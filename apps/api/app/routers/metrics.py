from __future__ import annotations

from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Response

from apps.api.app.db.connection import get_connection
from apps.api.app.security import Principal, require_permission
from apps.api.app.services.alerts import evaluate_alert_conditions
from apps.api.app.services.metrics import prometheus_lines, runtime_metrics

router = APIRouter(tags=["observability"])
AdminReadPrincipal = Annotated[Principal, Depends(require_permission("admin:read"))]


@router.get("/metrics", response_class=Response)
def metrics() -> Response:
    runtime = runtime_metrics.snapshot()
    database_metrics: dict[str, Any]
    try:
        with get_connection() as conn:
            database_metrics = collect_database_metrics(conn)
    except Exception:
        database_metrics = {"wellness_database_metrics_error": 1}
    return Response(
        content=prometheus_lines(runtime=runtime, database_metrics=database_metrics),
        media_type="text/plain; version=0.0.4",
    )


@router.get("/admin/observability")
def observability(
    _principal: AdminReadPrincipal,
) -> dict[str, Any]:
    runtime = runtime_metrics.snapshot()
    with get_connection() as conn:
        database_metrics = collect_database_metrics(conn)
        alerts = evaluate_alert_conditions(conn)
    return {
        "runtime": {
            "api_requests_total": runtime.requests_total,
            "api_errors_total": runtime.errors_total,
            "api_latency_ms_avg": runtime.latency_ms_avg,
            "map_query_latency_ms_avg": runtime.map_query_latency_ms_avg,
        },
        "database": database_metrics,
        "alerts": [
            {
                "condition": alert.condition,
                "firing": alert.firing,
                "severity": alert.severity,
                "summary": alert.summary,
                "details": alert.details,
            }
            for alert in alerts
        ],
    }


def collect_database_metrics(conn: Any) -> dict[str, Any]:
    source_status = cast(
        list[dict[str, Any]],
        conn.execute(
            """
            SELECT status::text AS label, count(*)::int AS count
            FROM source_run
            GROUP BY status
            """
        ).fetchall(),
    )
    record_totals = conn.execute(
        """
        SELECT
          COALESCE(sum(records_fetched), 0)::int AS fetched,
          COALESCE(sum(records_persisted), 0)::int AS persisted,
          COALESCE(sum(records_rejected), 0)::int AS rejected
        FROM source_run
        """
    ).fetchone()
    freshness = cast(
        list[dict[str, Any]],
        conn.execute(
            """
            WITH latest AS (
              SELECT DISTINCT ON (source_name)
                source_name,
                completed_at
              FROM source_run
              ORDER BY source_name, started_at DESC
            )
            SELECT
              sr.source_name AS label,
              COALESCE(EXTRACT(EPOCH FROM (now() - latest.completed_at)) / 3600, -1) AS age_hours
            FROM source_registry sr
            LEFT JOIN latest ON latest.source_name = sr.source_name
            WHERE sr.enabled = TRUE
            ORDER BY sr.source_name
            """
        ).fetchall(),
    )
    rejected_wa = conn.execute(
        """
        SELECT count(*)::int AS count
        FROM rejected_record
        WHERE reason ILIKE '%Washington%'
           OR reason ILIKE '%ZIP%'
           OR reason ILIKE '%Clark County%'
           OR reason ILIKE '%WA%'
        """
    ).fetchone()
    geocoding = conn.execute(
        """
        SELECT
          count(*)::int AS total,
          count(*) FILTER (WHERE geom IS NOT NULL)::int AS geocoded
        FROM "operator"
        """
    ).fetchone()
    contact_coverage = conn.execute(
        """
        SELECT
          count(*)::int AS total,
          count(*) FILTER (
            WHERE EXISTS (
              SELECT 1 FROM operator_contact oc WHERE oc.operator_id = op.id
            )
          )::int AS with_contact,
          count(*) FILTER (
            WHERE EXISTS (
              SELECT 1
              FROM operator_contact oc
              WHERE oc.operator_id = op.id AND oc.contact_type = 'phone'
            )
          )::int AS with_phone,
          count(*) FILTER (
            WHERE EXISTS (
              SELECT 1
              FROM operator_contact oc
              WHERE oc.operator_id = op.id AND oc.contact_type = 'email'
            )
          )::int AS with_email,
          count(*) FILTER (
            WHERE EXISTS (
              SELECT 1
              FROM operator_contact oc
              WHERE oc.operator_id = op.id AND oc.contact_type = 'website'
            )
          )::int AS with_website
        FROM "operator" op
        WHERE jsonb_array_length(op.source_refs) > 0
        """
    ).fetchone()
    fuzzy = cast(
        list[dict[str, Any]],
        conn.execute(
            """
            SELECT
              CASE
                WHEN confidence_score >= 0.9 THEN 'high'
                WHEN confidence_score >= 0.7 THEN 'medium'
                ELSE 'low'
              END AS label,
              count(*)::int AS count
            FROM entity_resolution_match
            GROUP BY 1
            """
        ).fetchall(),
    )
    ai = conn.execute(
        """
        SELECT count(*)::int AS enriched_count
        FROM signal
        WHERE cardinality(ai_generated_fields) > 0
        """
    ).fetchone()
    total = int(geocoding["total"] or 0)
    geocoded = int(geocoding["geocoded"] or 0)
    contact_total = int(contact_coverage["total"] or 0)
    with_contact = int(contact_coverage["with_contact"] or 0)
    return {
        "wellness_adapter_runs_total": {
            row["label"]: int(row["count"]) for row in source_status
        },
        "wellness_records_fetched_total": int(record_totals["fetched"] or 0),
        "wellness_records_persisted_total": int(record_totals["persisted"] or 0),
        "wellness_records_rejected_total": int(record_totals["rejected"] or 0),
        "wellness_source_freshness_age_hours": {
            row["label"]: round(float(row["age_hours"]), 3) for row in freshness
        },
        "wellness_wa_contamination_rejects_total": int(rejected_wa["count"] or 0),
        "wellness_geocoding_hit_rate": round(geocoded / total, 4) if total else 0,
        "wellness_contact_coverage": {
            "operator_count": contact_total,
            "with_contact_count": with_contact,
            "with_phone_count": int(contact_coverage["with_phone"] or 0),
            "with_email_count": int(contact_coverage["with_email"] or 0),
            "with_website_count": int(contact_coverage["with_website"] or 0),
            "coverage_ratio": round(with_contact / contact_total, 4) if contact_total else 0,
        },
        "wellness_fuzzy_match_confidence_bucket_total": {
            row["label"]: int(row["count"]) for row in fuzzy
        },
        "wellness_ai_estimated_cost_usd": 0,
        "wellness_ai_errors_total": 0,
        "wellness_ai_enriched_signals_total": int(ai["enriched_count"] or 0),
    }
