from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Query

from apps.api.app.db.connection import get_connection

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/source-runs")
def source_runs(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
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
def rejected_records(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
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
            {**row, "rejected_at": row["rejected_at"].isoformat()}
            for row in rows
        ],
        "meta": {"count": len(rows)},
    }


@router.get("/source-registry")
def source_registry() -> dict[str, Any]:
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
        "items": [
            {**row, "updated_at": row["updated_at"].isoformat()}
            for row in rows
        ],
        "meta": {"count": len(rows)},
    }


@router.get("/source-freshness")
def source_freshness() -> dict[str, Any]:
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
                  COALESCE(rejected.rejected_count, 0) AS rejected_count
                FROM source_registry sr
                LEFT JOIN latest ON latest.source_name = sr.source_name
                LEFT JOIN rejected ON rejected.source_name = sr.source_name
                WHERE sr.enabled = TRUE
                ORDER BY sr.phase ASC, sr.source_name ASC
                """
            ).fetchall(),
        )
    items = []
    stale_count = 0
    for row in rows:
        sla_hours = _sla_hours(str(row["cadence"]))
        completed_at = row["completed_at"]
        is_stale = completed_at is None
        if completed_at is not None:
            age_hours = _age_hours(completed_at)
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
                "sla_hours": sla_hours,
                "age_hours": age_hours,
                "is_stale": is_stale,
            }
        )
    return {"items": items, "meta": {"count": len(items), "stale_count": stale_count}}


def _sla_hours(cadence: str) -> int:
    lowered = cadence.lower()
    if "hour" in lowered:
        return 24
    if "daily" in lowered:
        return 36
    if "weekly" in lowered:
        return 24 * 8
    if "manual" in lowered:
        return 24 * 90
    return 24 * 14


def _age_hours(completed_at: Any) -> float:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    value = (
        completed_at
        if completed_at.tzinfo is not None
        else completed_at.replace(tzinfo=timezone.utc)
    )
    return (now - value).total_seconds() / 3600
