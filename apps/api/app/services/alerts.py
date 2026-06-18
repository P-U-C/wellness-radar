from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apps.api.app.config import settings

ALERT_CONDITIONS = [
    "source_stale_beyond_sla",
    "adapter_failed_twice",
    "rejected_record_spike",
    "api_health_failure",
    "no_signals_window",
    "migration_failure",
    "ai_cost_threshold",
]


@dataclass(frozen=True)
class AlertEvaluation:
    condition: str
    firing: bool
    severity: str
    summary: str
    details: dict[str, Any]


def evaluate_alert_conditions(conn: Any) -> list[AlertEvaluation]:
    return [
        *_source_stale(conn),
        *_adapter_failed_twice(conn),
        _rejected_record_spike(conn),
        _api_health(conn),
        _no_signals_window(conn),
        _migration_failure(conn),
        _ai_cost_threshold(conn),
    ]


def _source_stale(conn: Any) -> list[AlertEvaluation]:
    rows = conn.execute(
        """
        WITH latest AS (
          SELECT DISTINCT ON (source_name)
            source_name,
            completed_at
          FROM source_run
          ORDER BY source_name, started_at DESC
        )
        SELECT sr.source_name, sr.cadence, latest.completed_at
        FROM source_registry sr
        LEFT JOIN latest ON latest.source_name = sr.source_name
        WHERE sr.enabled = TRUE
        ORDER BY sr.source_name
        """
    ).fetchall()
    evaluations: list[AlertEvaluation] = []
    for row in rows:
        sla_hours = _sla_hours(str(row["cadence"]))
        completed_at = row["completed_at"]
        age_hours = None if completed_at is None else _age_hours(completed_at)
        firing = completed_at is None or (age_hours is not None and age_hours > sla_hours)
        evaluations.append(
            AlertEvaluation(
                condition="source_stale_beyond_sla",
                firing=firing,
                severity="warning" if firing else "ok",
                summary=f"{row['source_name']} freshness is {'stale' if firing else 'within SLA'}",
                details={
                    "source_name": row["source_name"],
                    "sla_hours": sla_hours,
                    "age_hours": age_hours,
                },
            )
        )
    return evaluations


def _adapter_failed_twice(conn: Any) -> list[AlertEvaluation]:
    rows = conn.execute(
        """
        WITH ranked AS (
          SELECT
            source_name,
            status::text AS status,
            row_number() OVER (PARTITION BY source_name ORDER BY started_at DESC) AS rank
          FROM source_run
        )
        SELECT source_name, bool_and(status = 'failed') AS failed_twice
        FROM ranked
        WHERE rank <= 2
        GROUP BY source_name
        HAVING count(*) = 2
        ORDER BY source_name
        """
    ).fetchall()
    evaluations = []
    for row in rows:
        failed_twice = bool(row["failed_twice"])
        state = "two failed runs" if failed_twice else "no two-failure streak"
        evaluations.append(
            AlertEvaluation(
                condition="adapter_failed_twice",
                firing=failed_twice,
                severity="critical" if failed_twice else "ok",
                summary=f"{row['source_name']} has {state}",
                details={"source_name": row["source_name"]},
            )
        )
    return evaluations


def _rejected_record_spike(conn: Any) -> AlertEvaluation:
    row = conn.execute(
        """
        SELECT
          count(*) FILTER (WHERE rejected_at >= now() - interval '24 hours')::int AS recent,
          GREATEST(
            count(*) FILTER (
              WHERE rejected_at < now() - interval '24 hours'
                AND rejected_at >= now() - interval '8 days'
            )::numeric / 7,
            1
          ) AS baseline
        FROM rejected_record
        """
    ).fetchone()
    recent = int(row["recent"] or 0)
    baseline = float(row["baseline"] or 1)
    firing = recent >= 10 and recent > baseline * 2
    return AlertEvaluation(
        condition="rejected_record_spike",
        firing=firing,
        severity="warning" if firing else "ok",
        summary=(
            "Rejected record volume spike detected"
            if firing
            else "Rejected record volume normal"
        ),
        details={"recent_24h": recent, "baseline_daily": baseline},
    )


def _api_health(conn: Any) -> AlertEvaluation:
    conn.execute("SELECT 1")
    return AlertEvaluation(
        condition="api_health_failure",
        firing=False,
        severity="ok",
        summary="API database health check passed",
        details={},
    )


def _no_signals_window(conn: Any) -> AlertEvaluation:
    row = conn.execute(
        """
        SELECT count(*)::int AS signal_count
        FROM signal
        WHERE ingested_at >= now() - interval '48 hours'
        """
    ).fetchone()
    count = int(row["signal_count"] or 0)
    return AlertEvaluation(
        condition="no_signals_window",
        firing=count == 0,
        severity="warning" if count == 0 else "ok",
        summary="No signals generated in 48 hours" if count == 0 else "Signals generated recently",
        details={"signal_count_48h": count},
    )


def _migration_failure(conn: Any) -> AlertEvaluation:
    applied = {
        str(row["version"])
        for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
    }
    migrations_dir = Path(__file__).parents[4] / "db" / "migrations"
    expected = {path.name for path in migrations_dir.glob("*.sql")}
    missing = sorted(expected - applied)
    return AlertEvaluation(
        condition="migration_failure",
        firing=bool(missing),
        severity="critical" if missing else "ok",
        summary="Database migrations missing" if missing else "Database migrations current",
        details={"missing": missing},
    )


def _ai_cost_threshold(conn: Any) -> AlertEvaluation:
    row = conn.execute(
        """
        SELECT count(*)::int AS enriched_count
        FROM signal
        WHERE cardinality(ai_generated_fields) > 0
        """
    ).fetchone()
    enriched_count = int(row["enriched_count"] or 0)
    estimated_cost_usd = 0.0
    firing = estimated_cost_usd > settings.ai_cost_alert_threshold_usd
    return AlertEvaluation(
        condition="ai_cost_threshold",
        firing=firing,
        severity="warning" if firing else "ok",
        summary="AI cost threshold exceeded" if firing else "AI cost within configured threshold",
        details={
            "estimated_cost_usd": estimated_cost_usd,
            "threshold_usd": settings.ai_cost_alert_threshold_usd,
            "enriched_signal_count": enriched_count,
        },
    )


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


def _age_hours(completed_at: datetime) -> float:
    value = completed_at if completed_at.tzinfo else completed_at.replace(tzinfo=timezone.utc)
    return round((datetime.now(timezone.utc) - value).total_seconds() / 3600, 3)
