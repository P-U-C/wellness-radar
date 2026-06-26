from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.app.routers import analytics

SOURCE_REF = {
    "source_name": "category_taxonomy",
    "url": "docs/analytics/category_naics_crosswalk.md",
    "trust_tier": "official",
    "seen_at": "2026-06-18T00:00:00Z",
    "source_record_id": "spa_thermal",
    "licence": None,
}


class FakeResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows


class FakeConn:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.queries: list[tuple[str, list[Any]]] = []

    def execute(self, query: str, params: list[Any] | None = None) -> FakeResult:
        self.queries.append((query, params or []))
        return FakeResult(self.rows)


def test_category_velocity_returns_numeric_zero_counts(monkeypatch) -> None:
    row = {
        "id": "velocity_spa_thermal_30",
        "category": "spa_thermal",
        "window_days": 30,
        "new_operator_count": 0,
        "job_velocity_count": 0,
        "event_velocity_count": 0,
        "news_velocity_count": 0,
        "component_breakdown": {
            "new_operator_count": 0,
            "job_velocity_count": 0,
            "event_velocity_count": 0,
            "news_velocity_count": 0,
            "window_days": 30,
            "source_confidence": 0.5,
        },
        "source_refs": [SOURCE_REF],
        "confidence_score": 0.5,
        "calculated_at": datetime(2026, 6, 26, 12, 0, tzinfo=timezone.utc),
    }
    fake_conn = FakeConn([row])

    @contextmanager
    def fake_connection() -> Iterator[FakeConn]:
        yield fake_conn

    monkeypatch.setattr(analytics, "get_connection", fake_connection)
    app = FastAPI()
    app.include_router(analytics.router)
    client = TestClient(app)

    response = client.get("/analytics/category-velocity?category=spa_thermal")

    assert response.status_code == 200
    body = response.json()
    item = body["items"][0]
    assert item["new_operator_count"] == 0
    assert item["event_velocity_count"] == 0
    assert isinstance(item["new_operator_count"], int)
    query, params = fake_conn.queries[0]
    assert "COALESCE(cv.new_operator_count, 0)" in query
    assert params == ["spa_thermal"]
