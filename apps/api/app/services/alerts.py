from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import httpx
from psycopg.types.json import Jsonb

from apps.api.app.config import settings
from packages.shared.cadence import sla_hours_for_cadence

ALERT_CONDITIONS = [
    "source_stale_beyond_sla",
    "adapter_run_failed",
    "adapter_failed_twice",
    "rejected_record_spike",
    "api_health_failure",
    "no_signals_window",
    "migration_failure",
    "ai_cost_threshold",
    "daily_market_brief",
]


@dataclass(frozen=True)
class AlertEvaluation:
    condition: str
    firing: bool
    severity: str
    summary: str
    details: dict[str, Any]


@dataclass(frozen=True)
class AlertDeliveryResult:
    status: str
    error_message: str | None = None


class AlertProvider(Protocol):
    name: str

    def dispatch(
        self,
        conn: Any,
        subscription: dict[str, Any],
        evaluation: AlertEvaluation,
    ) -> AlertDeliveryResult:
        ...


class DatabaseAlertProvider:
    name = "database"

    def __init__(self, *, status: str = "delivered") -> None:
        self.status = status

    def dispatch(
        self,
        conn: Any,
        subscription: dict[str, Any],
        evaluation: AlertEvaluation,
    ) -> AlertDeliveryResult:
        payload = alert_payload(
            subscription=subscription,
            evaluation=evaluation,
            provider=self.name,
            delivery_status=self.status,
        )
        _write_alert_dispatch(
            conn,
            subscription_id=str(subscription["id"]),
            evaluation=evaluation,
            status=self.status,
            payload=payload,
        )
        return AlertDeliveryResult(status=self.status)


class WebhookAlertProvider:
    name = "webhook"

    def __init__(
        self,
        url: str,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.url = url
        self.client = client
        self.timeout_seconds = timeout_seconds

    def dispatch(
        self,
        conn: Any,
        subscription: dict[str, Any],
        evaluation: AlertEvaluation,
    ) -> AlertDeliveryResult:
        payload = alert_payload(
            subscription=subscription,
            evaluation=evaluation,
            provider=self.name,
            delivery_status="pending",
        )
        status = "delivered"
        error_message: str | None = None
        response_status: int | None = None
        client = self.client or httpx.Client(timeout=self.timeout_seconds)
        try:
            response = client.post(self.url, json=payload)
            response_status = response.status_code
            response.raise_for_status()
        except Exception as exc:
            status = "failed"
            error_message = str(exc)
        finally:
            if self.client is None:
                client.close()

        persisted_payload = {
            **payload,
            "delivery_status": status,
            "webhook_status_code": response_status,
        }
        if error_message:
            persisted_payload["error_message"] = error_message
        _write_alert_dispatch(
            conn,
            subscription_id=str(subscription["id"]),
            evaluation=evaluation,
            status=status,
            payload=persisted_payload,
        )
        return AlertDeliveryResult(status=status, error_message=error_message)


def evaluate_alert_conditions(conn: Any) -> list[AlertEvaluation]:
    return [
        *_source_stale(conn),
        *_adapter_run_failed(conn),
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
          WHERE status = 'success'
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
        sla_hours = sla_hours_for_cadence(str(row["cadence"]))
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


def _adapter_run_failed(conn: Any) -> list[AlertEvaluation]:
    rows = conn.execute(
        """
        WITH latest AS (
          SELECT DISTINCT ON (source_name)
            source_name,
            status::text AS status,
            started_at,
            completed_at,
            error_message
          FROM source_run
          ORDER BY source_name, started_at DESC
        )
        SELECT
          sr.source_name,
          latest.status,
          latest.started_at,
          latest.completed_at,
          latest.error_message
        FROM source_registry sr
        JOIN latest ON latest.source_name = sr.source_name
        WHERE sr.enabled = TRUE
        ORDER BY sr.source_name
        """
    ).fetchall()
    evaluations: list[AlertEvaluation] = []
    for row in rows:
        failed = row["status"] == "failed"
        evaluations.append(
            AlertEvaluation(
                condition="adapter_run_failed",
                firing=failed,
                severity="critical" if failed else "ok",
                summary=(
                    f"{row['source_name']} latest adapter run failed"
                    if failed
                    else f"{row['source_name']} latest adapter run did not fail"
                ),
                details={
                    "source_name": row["source_name"],
                    "status": row["status"],
                    "started_at": _iso_or_none(row["started_at"]),
                    "completed_at": _iso_or_none(row["completed_at"]),
                    "error_message": row["error_message"],
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


def configured_alert_provider(
    *,
    webhook_url: str | None = None,
) -> AlertProvider:
    url = webhook_url if webhook_url is not None else settings.wr_alert_webhook_url
    if url:
        return WebhookAlertProvider(url)
    return DatabaseAlertProvider(status="delivered")


def dispatch_firing_alerts(
    conn: Any,
    *,
    provider: AlertProvider | None = None,
    evaluations: list[AlertEvaluation] | None = None,
) -> dict[str, int]:
    source = evaluations if evaluations is not None else evaluate_alert_conditions(conn)
    firing = [item for item in source if item.firing]
    return dispatch_alert_evaluations(conn, firing, provider=provider)


def dispatch_alert_evaluations(
    conn: Any,
    evaluations: list[AlertEvaluation],
    *,
    provider: AlertProvider | None = None,
) -> dict[str, int]:
    active_provider = provider or configured_alert_provider()
    subscriptions = _enabled_alert_subscriptions(conn)
    dispatch_count = 0
    failed_count = 0
    for subscription in subscriptions:
        subscribed = set(subscription["conditions"])
        for evaluation in evaluations:
            if evaluation.condition not in subscribed:
                continue
            result = active_provider.dispatch(conn, subscription, evaluation)
            dispatch_count += 1
            if result.status == "failed":
                failed_count += 1
    return {"dispatch_count": dispatch_count, "failed_count": failed_count}


def alert_payload(
    *,
    subscription: dict[str, Any],
    evaluation: AlertEvaluation,
    provider: str,
    delivery_status: str,
) -> dict[str, Any]:
    return {
        "subscription_id": subscription["id"],
        "condition": evaluation.condition,
        "severity": evaluation.severity,
        "summary": evaluation.summary,
        "details": evaluation.details,
        "channel": subscription.get("channel"),
        "target": subscription.get("target"),
        "provider": provider,
        "delivery_status": delivery_status,
        "fired_at": datetime.now(timezone.utc).isoformat(),
    }


def _enabled_alert_subscriptions(conn: Any) -> list[dict[str, Any]]:
    return list(
        conn.execute(
            """
            SELECT id, conditions, channel, target
            FROM alert_subscription
            WHERE enabled = TRUE
            """
        ).fetchall()
    )


def _write_alert_dispatch(
    conn: Any,
    *,
    subscription_id: str,
    evaluation: AlertEvaluation,
    status: str,
    payload: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO alert_dispatch (subscription_id, condition, status, payload)
        VALUES (%s, %s, %s, %s)
        """,
        (subscription_id, evaluation.condition, status, Jsonb(payload)),
    )


def _age_hours(completed_at: datetime) -> float:
    value = completed_at if completed_at.tzinfo else completed_at.replace(tzinfo=timezone.utc)
    return round((datetime.now(timezone.utc) - value).total_seconds() / 3600, 3)


def _iso_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
