from __future__ import annotations

import csv
import io
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from apps.api.app.db.connection import get_connection
from apps.api.app.security import ROLE_PERMISSIONS, Principal, require_permission
from apps.api.app.services.alerts import (
    ALERT_CONDITIONS,
    DatabaseAlertProvider,
    configured_alert_provider,
    dispatch_firing_alerts,
    evaluate_alert_conditions,
)
from apps.api.app.services.audit import audit_api_action
from packages.shared.cadence import sla_hours_for_cadence
from packages.shared.ids import stable_id

router = APIRouter(prefix="/admin", tags=["admin"])
AdminReadPrincipal = Annotated[Principal, Depends(require_permission("admin:read"))]
AdminWritePrincipal = Annotated[Principal, Depends(require_permission("admin:write"))]
ExportReadPrincipal = Annotated[Principal, Depends(require_permission("export:read"))]
SnapshotWritePrincipal = Annotated[Principal, Depends(require_permission("snapshot:write"))]
SubscriptionWritePrincipal = Annotated[
    Principal,
    Depends(require_permission("subscription:write")),
]


class AlertSubscriptionPayload(BaseModel):
    owner_email: str
    name: str = Field(min_length=2, max_length=120)
    categories: list[str] = Field(default_factory=list)
    geography: dict[str, Any] = Field(default_factory=dict)
    conditions: list[str] = Field(default_factory=lambda: ALERT_CONDITIONS.copy())
    channel: str = "dispatch_stub"
    target: str | None = None


class SnapshotPayload(BaseModel):
    snapshot_type: Literal["operators", "signals", "graph"]
    format: Literal["json", "csv"] = "json"


@router.get("/me")
def admin_me(
    principal: AdminReadPrincipal,
) -> dict[str, Any]:
    return {
        "role": principal.role,
        "actor_id": principal.actor_id,
        "permissions": sorted(ROLE_PERMISSIONS[principal.role]),
    }


@router.get("/source-runs")
def source_runs(
    _principal: AdminReadPrincipal,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(
                """
                SELECT
                  id,
                  source_name,
                  status::text AS status,
                  started_at,
                  completed_at,
                  records_fetched,
                  records_persisted,
                  records_rejected,
                  error_count,
                  error_message
                FROM source_run
                ORDER BY started_at DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall(),
        )
    return {
        "items": [
            {
                **row,
                "started_at": row["started_at"].isoformat(),
                "completed_at": row["completed_at"].isoformat()
                if row["completed_at"] is not None
                else None,
            }
            for row in rows
        ],
        "meta": {"count": len(rows)},
    }


@router.get("/rejected-records")
def rejected_records(
    _principal: AdminReadPrincipal,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(
                """
                SELECT id, source_name, reason, raw_payload_id, raw, rejected_at
                FROM rejected_record
                ORDER BY rejected_at DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall(),
        )
    return {
        "items": [
            {**row, "rejected_at": row["rejected_at"].isoformat()} for row in rows
        ],
        "meta": {"count": len(rows)},
    }


@router.get("/source-registry")
def source_registry(
    _principal: AdminReadPrincipal,
) -> dict[str, Any]:
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(
                """
                SELECT
                  source_name,
                  family,
                  base_url,
                  cadence,
                  licence,
                  cost,
                  trust_tier::text AS trust_tier,
                  geo_rule,
                  phase,
                  rights_notes,
                  enabled,
                  updated_at
                FROM source_registry
                ORDER BY phase ASC, source_name ASC
                """
            ).fetchall(),
        )
    return {
        "items": [{**row, "updated_at": row["updated_at"].isoformat()} for row in rows],
        "meta": {
            "count": len(rows),
            "needs_review_count": sum(
                1 for row in rows if "needs_review" in str(row["rights_notes"])
            ),
        },
    }


@router.get("/source-freshness")
def source_freshness(
    _principal: AdminReadPrincipal,
) -> dict[str, Any]:
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(
                """
                WITH latest AS (
                  SELECT DISTINCT ON (source_name)
                    source_name,
                    id AS latest_run_id,
                    status::text AS latest_status,
                    started_at,
                    completed_at,
                    records_fetched,
                    records_persisted,
                    records_rejected,
                    error_count,
                    error_message
                  FROM source_run
                  ORDER BY source_name, started_at DESC
                ),
                latest_success AS (
                  SELECT DISTINCT ON (source_name)
                    source_name,
                    completed_at AS last_success_completed_at
                  FROM source_run
                  WHERE status = 'success'
                  ORDER BY source_name, completed_at DESC
                ),
                rejected AS (
                  SELECT source_name, count(*)::int AS rejected_count
                  FROM rejected_record
                  GROUP BY source_name
                )
                SELECT
                  sr.source_name,
                  sr.family,
                  sr.cadence,
                  sr.trust_tier::text AS trust_tier,
                  sr.enabled,
                  latest.latest_run_id,
                  latest.latest_status,
                  latest.started_at,
                  latest.completed_at,
                  latest.records_fetched,
                  latest.records_persisted,
                  latest.records_rejected,
                  latest.error_count,
                  latest.error_message,
                  latest_success.last_success_completed_at,
                  COALESCE(rejected.rejected_count, 0) AS rejected_count
                FROM source_registry sr
                LEFT JOIN latest ON latest.source_name = sr.source_name
                LEFT JOIN latest_success ON latest_success.source_name = sr.source_name
                LEFT JOIN rejected ON rejected.source_name = sr.source_name
                WHERE sr.enabled = TRUE
                ORDER BY sr.phase ASC, sr.source_name ASC
                """
            ).fetchall(),
        )
    items = []
    stale_count = 0
    for row in rows:
        sla_hours = sla_hours_for_cadence(str(row["cadence"]))
        completed_at = row["completed_at"]
        last_success_completed_at = row["last_success_completed_at"]
        is_stale = last_success_completed_at is None
        if last_success_completed_at is not None:
            age_hours = _age_hours(last_success_completed_at)
            is_stale = age_hours > sla_hours
        else:
            age_hours = None
        if is_stale:
            stale_count += 1
        items.append(
            {
                **row,
                "started_at": row["started_at"].isoformat()
                if row["started_at"] is not None
                else None,
                "completed_at": completed_at.isoformat() if completed_at is not None else None,
                "last_success_completed_at": last_success_completed_at.isoformat()
                if last_success_completed_at is not None
                else None,
                "sla_hours": sla_hours,
                "age_hours": age_hours,
                "is_stale": is_stale,
            }
        )
    return {"items": items, "meta": {"count": len(items), "stale_count": stale_count}}


@router.get("/audit-logs")
def audit_logs(
    _principal: AdminReadPrincipal,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(
                """
                SELECT
                  id,
                  occurred_at,
                  action,
                  actor_role,
                  actor_id,
                  request_id,
                  source_name,
                  source_run_id,
                  entity_type,
                  entity_id,
                  source_event_id,
                  signal_id,
                  reject_reason,
                  prompt_version,
                  metadata
                FROM audit_log
                ORDER BY occurred_at DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall(),
        )
    return {
        "items": [{**row, "occurred_at": row["occurred_at"].isoformat()} for row in rows],
        "meta": {"count": len(rows)},
    }


@router.get("/alert-subscriptions")
def list_alert_subscriptions(
    _principal: AdminReadPrincipal,
) -> dict[str, Any]:
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(
                """
                SELECT
                  id,
                  owner_email,
                  name,
                  categories,
                  geography,
                  conditions,
                  channel,
                  target,
                  enabled,
                  created_at,
                  updated_at
                FROM alert_subscription
                ORDER BY created_at DESC
                """
            ).fetchall(),
        )
    return {
        "items": [
            {
                **row,
                "created_at": row["created_at"].isoformat(),
                "updated_at": row["updated_at"].isoformat(),
            }
            for row in rows
        ],
        "meta": {"count": len(rows), "conditions": ALERT_CONDITIONS},
    }


@router.post("/alert-subscriptions", status_code=201)
def create_alert_subscription(
    payload: AlertSubscriptionPayload,
    request: Request,
    principal: SubscriptionWritePrincipal,
) -> dict[str, Any]:
    invalid = sorted(set(payload.conditions) - set(ALERT_CONDITIONS))
    if invalid:
        raise HTTPException(status_code=422, detail=f"invalid alert conditions: {invalid}")
    subscription_id = stable_id(
        "alert_subscription",
        payload.owner_email,
        payload.name,
        ",".join(sorted(payload.categories)),
        ",".join(sorted(payload.conditions)),
    )
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO alert_subscription (
              id,
              owner_email,
              name,
              categories,
              geography,
              conditions,
              channel,
              target,
              created_by_role
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
              categories = EXCLUDED.categories,
              geography = EXCLUDED.geography,
              conditions = EXCLUDED.conditions,
              channel = EXCLUDED.channel,
              target = EXCLUDED.target,
              enabled = TRUE,
              updated_at = now()
            """,
            (
                subscription_id,
                payload.owner_email,
                payload.name,
                payload.categories,
                Jsonb(payload.geography),
                payload.conditions,
                payload.channel,
                payload.target,
                principal.role,
            ),
        )
        audit_api_action(
            conn,
            request=request,
            principal=principal,
            action="alert_subscription_saved",
            entity_type="alert_subscription",
            entity_id=subscription_id,
            metadata=payload.model_dump(),
        )
    return {"id": subscription_id, "status": "enabled"}


@router.get("/alerts/evaluate")
def evaluate_alerts(
    _principal: AdminReadPrincipal,
) -> dict[str, Any]:
    with get_connection() as conn:
        evaluations = evaluate_alert_conditions(conn)
    return {
        "items": [
            {
                "condition": item.condition,
                "firing": item.firing,
                "severity": item.severity,
                "summary": item.summary,
                "details": item.details,
            }
            for item in evaluations
        ],
        "meta": {
            "count": len(evaluations),
            "firing_count": sum(1 for item in evaluations if item.firing),
        },
    }


@router.post("/alerts/dispatch-stub", status_code=202)
def dispatch_alert_stub(
    request: Request,
    principal: AdminWritePrincipal,
) -> dict[str, Any]:
    with get_connection() as conn:
        result = dispatch_firing_alerts(
            conn,
            provider=DatabaseAlertProvider(status="stubbed"),
        )
        audit_api_action(
            conn,
            request=request,
            principal=principal,
            action="alert_dispatch_stubbed",
            metadata=result,
        )
    return {"status": "stubbed", **result}


@router.post("/alerts/dispatch", status_code=202)
def dispatch_alerts(
    request: Request,
    principal: AdminWritePrincipal,
) -> dict[str, Any]:
    provider = configured_alert_provider()
    with get_connection() as conn:
        result = dispatch_firing_alerts(conn, provider=provider)
        audit_api_action(
            conn,
            request=request,
            principal=principal,
            action="alert_dispatched",
            metadata={"provider": provider.name, **result},
        )
    status = "failed" if result["failed_count"] else "delivered"
    return {"status": status, "provider": provider.name, **result}


@router.get("/exports/{dataset}", response_model=None)
def export_dataset(
    dataset: Literal["operators", "signals", "graph"],
    _principal: ExportReadPrincipal,
    format: Literal["json", "csv"] = Query(default="json"),
) -> Any:
    rows = _export_rows(dataset)
    if format == "json":
        return {"dataset": dataset, "items": rows, "meta": {"count": len(rows)}}
    return Response(
        content=_rows_to_csv(rows),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{dataset}.csv"'},
    )


@router.get("/snapshots")
def list_snapshots(
    _principal: AdminReadPrincipal,
) -> dict[str, Any]:
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(
                """
                SELECT
                  id,
                  snapshot_type,
                  format,
                  status,
                  requested_by,
                  row_count,
                  manifest,
                  created_at
                FROM export_snapshot
                ORDER BY created_at DESC
                LIMIT 100
                """
            ).fetchall(),
        )
    return {
        "items": [{**row, "created_at": row["created_at"].isoformat()} for row in rows],
        "meta": {"count": len(rows)},
    }


@router.post("/snapshots", status_code=201)
def create_snapshot(
    payload: SnapshotPayload,
    request: Request,
    principal: SnapshotWritePrincipal,
) -> dict[str, Any]:
    rows = _export_rows(payload.snapshot_type)
    snapshot_id = stable_id(
        "snapshot",
        payload.snapshot_type,
        payload.format,
        principal.actor_id,
        str(len(rows)),
    )
    manifest = {
        "snapshot_type": payload.snapshot_type,
        "format": payload.format,
        "row_count": len(rows),
        "sample_ids": [str(row.get("id") or row.get("record_id")) for row in rows[:10]],
    }
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO export_snapshot (
              id,
              snapshot_type,
              format,
              status,
              requested_by,
              row_count,
              manifest
            )
            VALUES (%s, %s, %s, 'ready', %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
              created_at = now(),
              row_count = EXCLUDED.row_count,
              manifest = EXCLUDED.manifest
            """,
            (
                snapshot_id,
                payload.snapshot_type,
                payload.format,
                principal.actor_id,
                len(rows),
                Jsonb(manifest),
            ),
        )
        audit_api_action(
            conn,
            request=request,
            principal=principal,
            action="snapshot_created",
            entity_type="export_snapshot",
            entity_id=snapshot_id,
            metadata=manifest,
        )
    return {"id": snapshot_id, "status": "ready", "manifest": manifest}


def _export_rows(dataset: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        if dataset == "operators":
            return cast(
                list[dict[str, Any]],
                conn.execute(
                    """
                    SELECT
                      id,
                      name,
                      categories,
                      status::text AS status,
                      address,
                      municipality,
                      neighborhood,
                      ST_Y(geom::geometry) AS lat,
                      ST_X(geom::geometry) AS lng,
                      confidence_score,
                      source_refs,
                      last_seen_at AS freshness_at
                    FROM "operator"
                    WHERE jsonb_array_length(source_refs) > 0
                    ORDER BY last_seen_at DESC, name ASC
                    """
                ).fetchall(),
            )
        if dataset == "signals":
            return cast(
                list[dict[str, Any]],
                conn.execute(
                    """
                    SELECT
                      id,
                      type,
                      severity::text AS severity,
                      title,
                      source_name,
                      trust_tier::text AS trust_tier,
                      occurred_at,
                      related_operator_id,
                      confidence_score,
                      source_refs,
                      ingested_at AS freshness_at
                    FROM signal
                    WHERE jsonb_array_length(source_refs) > 0
                    ORDER BY occurred_at DESC
                    """
                ).fetchall(),
            )
        if dataset == "graph":
            nodes = cast(
                list[dict[str, Any]],
                conn.execute(
                    """
                    SELECT
                      id AS record_id,
                      'node' AS record_type,
                      node_type AS graph_type,
                      entity_id,
                      label,
                      centrality,
                      community,
                      source_refs,
                      confidence_score
                    FROM entity_graph_node
                    WHERE jsonb_array_length(source_refs) > 0
                    ORDER BY node_type, label
                    """
                ).fetchall(),
            )
            edges = cast(
                list[dict[str, Any]],
                conn.execute(
                    """
                    SELECT
                      id AS record_id,
                      'edge' AS record_type,
                      edge_type AS graph_type,
                      source_node_id AS entity_id,
                      target_node_id AS label,
                      weight AS centrality,
                      NULL::int AS community,
                      source_refs,
                      confidence_score
                    FROM entity_graph_edge
                    WHERE jsonb_array_length(source_refs) > 0
                    ORDER BY edge_type, id
                    """
                ).fetchall(),
            )
            return [*nodes, *edges]
    raise HTTPException(status_code=404, detail="unknown export dataset")


def _rows_to_csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    output = io.StringIO()
    fieldnames = sorted({key for row in rows for key in row})
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _csv_value(row.get(key)) for key in fieldnames})
    return output.getvalue()


def _csv_value(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        return str(value)
    return value


def _age_hours(completed_at: Any) -> float:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    value = (
        completed_at
        if completed_at.tzinfo is not None
        else completed_at.replace(tzinfo=timezone.utc)
    )
    return (now - value).total_seconds() / 3600
