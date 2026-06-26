from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.app.routers import operators

SOURCE_REF = {
    "source_name": "municipal_facilities",
    "url": "https://example.test/operator",
    "trust_tier": "official",
    "seen_at": "2026-06-22T00:00:00Z",
    "source_record_id": "operator-1",
    "licence": "fixture",
}


class FakeResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows

    def fetchone(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None


class FakeConn:
    def __init__(self, result_sets: list[list[dict[str, Any]]]) -> None:
        self.result_sets = result_sets
        self.queries: list[tuple[str, Any]] = []

    def execute(self, query: str, params: Any = None) -> FakeResult:
        self.queries.append((query, params))
        return FakeResult(self.result_sets.pop(0))


def test_operators_filter_by_venue_class(monkeypatch) -> None:
    fake_conn = FakeConn(
        [
            [_operator_row()],
            [{"operator_count": 1, "with_contact_count": 0, "municipality_count": 1}],
            [{"municipality": "Vancouver", "operator_count": 1}],
        ]
    )

    @contextmanager
    def fake_connection() -> Iterator[FakeConn]:
        yield fake_conn

    monkeypatch.setattr(operators, "get_connection", fake_connection)
    app = FastAPI()
    app.include_router(operators.router)
    client = TestClient(app)

    response = client.get("/operators?venue_class=public_recreation&limit=5")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["venue_class"] == "public_recreation"
    assert body["meta"]["municipality_coverage"]["municipality_count"] == 1
    assert body["meta"]["municipality_coverage"]["municipalities"] == [
        {"name": "Vancouver", "operator_count": 1}
    ]
    assert body["items"][0]["venue_class"] == "public_recreation"
    assert body["items"][0]["operator_class"] == "public_recreation"
    assert body["items"][0]["regulated"] is False
    assert body["items"][0]["is_mobile"] is False
    assert body["items"][0]["service_area"] is None
    assert body["items"][0]["primary_bundles"][0]["slug"] == "public-recreation-courts-fields"
    query, params = fake_conn.queries[0]
    assert "op.venue_class = %s" in query
    assert params[-2:] == ["public_recreation", 5]


def _operator_row() -> dict[str, Any]:
    return {
        "id": "op_pitch",
        "name": "Empire Fields",
        "categories": ["field_track_sports", "public_recreation"],
        "venue_class": "public_recreation",
        "operator_class": "public_recreation",
        "regulated": False,
        "status": "open",
        "address": "2901 East Hastings Street, Vancouver, BC",
        "municipality": "Vancouver",
        "neighborhood": "Hastings-Sunrise",
        "phone": None,
        "website": None,
        "social_links": {},
        "organization_id": None,
        "orgbook_id": None,
        "neighborhood_assignment_method": None,
        "neighborhood_assignment_source": None,
        "neighborhood_assignment_confidence": None,
        "is_mobile": False,
        "service_area": None,
        "primary_bundles": [
            {
                "id": "bundle_public_recreation_courts_fields",
                "slug": "public-recreation-courts-fields",
                "label": "Public recreation courts & fields",
                "confidence_score": 0.9,
                "source_refs": [SOURCE_REF],
            }
        ],
        "lat": 49.285,
        "lng": -123.036,
        "confidence_score": 0.88,
        "source_refs": [SOURCE_REF],
        "last_seen_at": datetime(2026, 6, 22, 12, 0, tzinfo=timezone.utc),
        "contacts": [],
    }
