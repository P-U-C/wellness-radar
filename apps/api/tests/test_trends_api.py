from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.app.routers import trends

SOURCE_REF = {
    "source_name": "gdelt_doc",
    "url": "https://api.gdeltproject.org/api/v2/doc/doc",
    "trust_tier": "community",
    "seen_at": "2026-06-26T00:00:00Z",
    "source_record_id": "trend_live",
    "licence": "GDELT Project terms",
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


def test_trends_hides_stub_breakout_rows_by_default(monkeypatch) -> None:
    fake_conn = FakeConn(
        [
            _trend_row("cold plunge", "Vancouver", "breakout", is_stub=True),
            _trend_row("sauna", "Vancouver", "rising", is_stub=False),
        ]
    )

    @contextmanager
    def fake_connection() -> Iterator[FakeConn]:
        yield fake_conn

    monkeypatch.setattr(trends, "get_connection", fake_connection)
    app = FastAPI()
    app.include_router(trends.router)
    client = TestClient(app)

    response = client.get("/trends")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["count"] == 1
    assert body["meta"]["hidden_stub_count"] == 1
    assert body["meta"]["status"] == "live"
    assert body["items"][0]["term"] == "sauna"
    assert body["items"][0]["is_stub"] is False
    assert body["items"][0]["growth_class"] == "rising"
    assert all(item["growth_class"] != "breakout" for item in body["items"])


def test_trends_returns_explicit_pending_when_only_fixture_rows_exist(monkeypatch) -> None:
    fake_conn = FakeConn([_trend_row("cold plunge", "Vancouver", "breakout", is_stub=True)])

    @contextmanager
    def fake_connection() -> Iterator[FakeConn]:
        yield fake_conn

    monkeypatch.setattr(trends, "get_connection", fake_connection)
    app = FastAPI()
    app.include_router(trends.router)
    client = TestClient(app)

    response = client.get("/trends?term=cold%20plunge")

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["meta"]["status"] == "data_pending"
    assert body["meta"]["hidden_stub_count"] == 1
    assert "Fixture peer-city trend rows are hidden" in body["meta"]["pending_reason"]


def _trend_row(term: str, city: str, growth_class: str, *, is_stub: bool) -> dict[str, Any]:
    return {
        "term": term,
        "city": city,
        "geography_code": "CA-BC-Vancouver",
        "growth_class": growth_class,
        "series": [{"period": "w01", "value": 10}, {"period": "w02", "value": 80}],
        "source_name": "peer_city_trends_fixture" if is_stub else "gdelt_doc",
        "fetched_at": datetime(2026, 6, 26, 12, 0, tzinfo=timezone.utc),
        "source_refs": [SOURCE_REF],
        "confidence_score": 0.62,
        "is_stub": is_stub,
        "methodology": "Test trend row.",
    }
