from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.app.routers import operators


class FakeResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows

    def fetchone(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None


class FakeConn:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.queries: list[tuple[str, Any]] = []

    def execute(self, query: str, params: list[Any] | None = None) -> FakeResult:
        self.queries.append((query, params))
        return FakeResult(self.rows)


SOURCE_REF = {
    "source_name": "manual_seed",
    "url": "https://example.test/operator",
    "trust_tier": "informal",
    "seen_at": "2026-06-22T00:00:00Z",
    "source_record_id": "operator-1",
    "licence": "fixture",
}


def test_leads_return_neighborhood_and_contact_type(monkeypatch) -> None:
    row = _lead_db_row()

    @contextmanager
    def fake_connection() -> Iterator[FakeConn]:
        yield FakeConn([row])

    monkeypatch.setattr(operators, "get_connection", fake_connection)
    app = FastAPI()
    app.include_router(operators.router)
    client = TestClient(app)

    response = client.get("/leads?limit=500")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["neighborhood"] == "Mount Pleasant"
    assert item["category"] == "recovery_contrast_therapy"
    assert item["contacts"][0]["contact_type"] == "website"


def test_leads_support_category_and_bundle_filters(monkeypatch) -> None:
    row = _lead_db_row()
    fake_conn = FakeConn([row])

    @contextmanager
    def fake_connection() -> Iterator[FakeConn]:
        yield fake_conn

    monkeypatch.setattr(operators, "get_connection", fake_connection)
    app = FastAPI()
    app.include_router(operators.router)
    client = TestClient(app)

    response = client.get(
        "/leads?category=recovery_contrast_therapy&bundle=cold-plunge-contrast-therapy"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["category"] == "recovery_contrast_therapy"
    assert body["meta"]["bundle"] == "cold-plunge-contrast-therapy"
    assert body["items"][0]["category"] == "recovery_contrast_therapy"
    query, params = fake_conn.queries[0]
    assert "bundle_operator_membership" in query
    assert params[:3] == [
        "recovery_contrast_therapy",
        "cold-plunge-contrast-therapy",
        "cold-plunge-contrast-therapy",
    ]


def test_lead_detail_returns_source_backed_lead(monkeypatch) -> None:
    row = _lead_db_row()

    @contextmanager
    def fake_connection() -> Iterator[FakeConn]:
        yield FakeConn([row])

    monkeypatch.setattr(operators, "get_connection", fake_connection)
    app = FastAPI()
    app.include_router(operators.router)
    client = TestClient(app)

    response = client.get("/leads/op_tality")

    assert response.status_code == 200
    item = response.json()
    assert item["id"] == "op_tality"
    assert item["category"] == "recovery_contrast_therapy"
    assert item["source_refs"] == [SOURCE_REF]


def test_leads_csv_export_is_public(monkeypatch) -> None:
    row = _lead_db_row()

    @contextmanager
    def fake_connection() -> Iterator[FakeConn]:
        yield FakeConn([row])

    monkeypatch.setattr(operators, "get_connection", fake_connection)
    app = FastAPI()
    app.include_router(operators.router)
    client = TestClient(app)

    response = client.get("/leads?format=csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "contact_type" in response.text
    assert "Mount Pleasant" in response.text
    assert "website" in response.text


def _lead_db_row() -> dict[str, Any]:
    return {
        "id": "op_tality",
        "name": "Tality Wellness Mount Pleasant",
        "categories": ["recovery_contrast_therapy", "community_social_wellness"],
        "venue_class": "commercial_wellness",
        "status": "open",
        "address": "107 East 3rd Avenue, Vancouver, BC",
        "municipality": "Vancouver",
        "neighborhood": "Mount Pleasant",
        "phone": None,
        "website": "https://www.talitywellness.ca/",
        "social_links": {},
        "organization_id": None,
        "orgbook_id": None,
        "lat": 49.2676,
        "lng": -123.1018,
        "confidence_score": 0.82,
        "source_refs": [SOURCE_REF],
        "last_seen_at": datetime(2026, 6, 22, 12, 0, tzinfo=timezone.utc),
        "contacts": [
            {
                "type": "website",
                "contact_type": "website",
                "value": "https://www.talitywellness.ca/",
                "platform": None,
                "source_ref": SOURCE_REF,
                "confidence": 0.82,
            }
        ],
        "contact_count": 1,
        "signal_count": 0,
        "opportunity_geo_name": "Mount Pleasant",
        "opportunity_score": 0.78,
        "opportunity_source_refs": [SOURCE_REF],
    }
