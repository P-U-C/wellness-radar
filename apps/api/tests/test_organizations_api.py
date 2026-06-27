from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.app.routers import organizations

SOURCE_REF = {
    "source_name": "orgbook_bc",
    "url": "https://orgbook.gov.bc.ca/entity/2381381",
    "trust_tier": "official",
    "seen_at": "2026-06-26T00:00:00Z",
    "source_record_id": "2381381",
    "licence": "BC Gov public registry access terms",
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


def test_organizations_endpoint_returns_orgbook_firmographics(monkeypatch) -> None:
    row = {
        "id": "org_2381381",
        "name": "TALITY WELLNESS LTD.",
        "registry_id": "BC1234567",
        "orgbook_id": "2381381",
        "organization_type": "BC Company",
        "website": "https://www.talitywellness.ca/",
        "location": {
            "operator_id": "op_tality",
            "operator_name": "Tality Wellness",
            "address": "107 East 3rd Avenue, Vancouver, BC",
            "municipality": "Vancouver",
            "neighborhood": "Mount Pleasant",
            "lat": 49.2676,
            "lng": -123.1018,
            "source_refs": [SOURCE_REF],
        },
        "headcount": None,
        "industry": None,
        "industry_code": None,
        "source_refs": [SOURCE_REF],
        "firmographic_source_refs": [],
        "confidence_score": 0.88,
        "last_seen_at": datetime(2026, 6, 26, 12, 0, tzinfo=timezone.utc),
    }
    fake_conn = FakeConn([row])

    @contextmanager
    def fake_connection() -> Iterator[FakeConn]:
        yield fake_conn

    monkeypatch.setattr(organizations, "get_connection", fake_connection)
    app = FastAPI()
    app.include_router(organizations.router)
    client = TestClient(app)

    response = client.get("/employers?limit=500")

    assert response.status_code == 200
    body = response.json()
    item = body["items"][0]
    assert body["meta"]["limit"] == 500
    assert body["meta"]["role"] == "employer"
    assert item["role"] == "employer"
    assert item["name"] == "TALITY WELLNESS LTD."
    assert item["registry_id"] == "BC1234567"
    assert item["location"]["municipality"] == "Vancouver"
    assert item["headcount"] is None
    assert item["industry"] is None
    assert item["source_refs"] == [SOURCE_REF]
    query, params = fake_conn.queries[0]
    assert "org.orgbook_id IS NOT NULL" in query
    assert params == [500]
