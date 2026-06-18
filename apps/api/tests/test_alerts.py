from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from apps.api.app.services import alerts
from apps.api.app.services.alerts import (
    ALERT_CONDITIONS,
    AlertEvaluation,
    DatabaseAlertProvider,
    WebhookAlertProvider,
    dispatch_alert_evaluations,
)


def test_alert_condition_catalog_covers_production_conditions() -> None:
    assert set(ALERT_CONDITIONS) == {
        "source_stale_beyond_sla",
        "adapter_run_failed",
        "adapter_failed_twice",
        "rejected_record_spike",
        "api_health_failure",
        "no_signals_window",
        "migration_failure",
        "ai_cost_threshold",
    }


class FakeResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows


class FakeConn:
    def __init__(self) -> None:
        self.inserted: list[tuple[Any, ...] | None] = []
        self.queries: list[str] = []

    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> FakeResult:
        self.queries.append(query)
        if "INSERT INTO alert_dispatch" in query:
            self.inserted.append(params)
            return FakeResult([])
        if "FROM alert_subscription" in query:
            return FakeResult(
                [
                    {
                        "id": "sub-1",
                        "conditions": ["source_stale_beyond_sla", "adapter_run_failed"],
                        "channel": "dispatch_stub",
                        "target": None,
                    }
                ]
            )
        return FakeResult(
            [
                {
                    "source_name": "local_rss",
                    "cadence": "hourly/daily",
                    "completed_at": datetime.now(timezone.utc) - timedelta(hours=30),
                },
                {
                    "source_name": "osm_overpass",
                    "cadence": "weekly",
                    "completed_at": datetime.now(timezone.utc) - timedelta(hours=2),
                },
            ]
        )


def test_stale_source_evaluation_dispatches_alert_for_last_success_sla() -> None:
    conn = FakeConn()

    evaluations = [item for item in alerts._source_stale(conn) if item.firing]
    result = dispatch_alert_evaluations(
        conn,
        evaluations,
        provider=DatabaseAlertProvider(status="delivered"),
    )

    assert result == {"dispatch_count": 1, "failed_count": 0}
    assert evaluations[0].condition == "source_stale_beyond_sla"
    assert evaluations[0].details["source_name"] == "local_rss"
    assert conn.inserted[0] is not None
    assert conn.inserted[0][1] == "source_stale_beyond_sla"
    assert conn.inserted[0][2] == "delivered"
    assert "WHERE status = 'success'" in conn.queries[0]


class FakeWebhookResponse:
    def __init__(self, status_code: int = 204, *, fails: bool = False) -> None:
        self.status_code = status_code
        self.fails = fails

    def raise_for_status(self) -> None:
        if self.fails:
            raise RuntimeError("webhook failed")


class FakeWebhookClient:
    def __init__(self, response: FakeWebhookResponse) -> None:
        self.response = response
        self.requests: list[dict[str, Any]] = []

    def post(self, url: str, json: dict[str, Any]) -> FakeWebhookResponse:
        self.requests.append({"url": url, "json": json})
        return self.response


def test_webhook_provider_posts_json_and_records_delivery_status() -> None:
    evaluation = AlertEvaluation(
        condition="adapter_run_failed",
        firing=True,
        severity="critical",
        summary="local_rss adapter run failed",
        details={"source_name": "local_rss"},
    )
    subscription = {
        "id": "sub-1",
        "conditions": ["adapter_run_failed"],
        "channel": "webhook",
        "target": None,
    }
    conn = FakeConn()
    client = FakeWebhookClient(FakeWebhookResponse(status_code=204))

    result = WebhookAlertProvider(
        "https://example.test/webhook",
        client=client,  # type: ignore[arg-type]
    ).dispatch(conn, subscription, evaluation)

    assert result.status == "delivered"
    assert client.requests[0]["url"] == "https://example.test/webhook"
    assert client.requests[0]["json"]["condition"] == "adapter_run_failed"
    assert conn.inserted[0] is not None
    assert conn.inserted[0][2] == "delivered"


def test_webhook_provider_records_failed_post_without_raising() -> None:
    evaluation = AlertEvaluation(
        condition="adapter_run_failed",
        firing=True,
        severity="critical",
        summary="local_rss adapter run failed",
        details={"source_name": "local_rss"},
    )
    subscription = {
        "id": "sub-1",
        "conditions": ["adapter_run_failed"],
        "channel": "webhook",
        "target": None,
    }
    conn = FakeConn()
    client = FakeWebhookClient(FakeWebhookResponse(status_code=500, fails=True))

    result = WebhookAlertProvider(
        "https://example.test/webhook",
        client=client,  # type: ignore[arg-type]
    ).dispatch(conn, subscription, evaluation)

    assert result.status == "failed"
    assert result.error_message == "webhook failed"
    assert conn.inserted[0] is not None
    assert conn.inserted[0][2] == "failed"
