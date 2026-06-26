from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.app.routers import people


class FakeResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows


class FakeConn:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.params: list[tuple[Any, ...]] = []

    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> FakeResult:
        self.params.append(params or ())
        return FakeResult(self.rows)


SOURCE_REF = {
    "source_name": "manual_people_csv",
    "url": "https://example.test/person",
    "trust_tier": "informal",
    "seen_at": "2026-06-22T00:00:00Z",
    "source_record_id": "person-1",
    "licence": "fixture",
}


def test_people_limit_clamps_and_contactability_is_explicit(monkeypatch) -> None:
    row = {
        "id": "person_policy",
        "name": "Example Minister",
        "roles": ["Minister of Health"],
        "affiliations": [
            {"organization_name": "Government of British Columbia", "role": "Minister"}
        ],
        "public_profiles": {"primary": "https://example.test/person"},
        "influence_score": 0.7,
        "locality_score": 1.0,
        "confidence_score": 0.95,
        "source_refs": [SOURCE_REF],
        "last_seen_at": datetime(2026, 6, 22, 12, 0, tzinfo=timezone.utc),
        "influence_components": None,
        "influence_explanation": None,
        "influence_methodology_version": None,
        "influence_source_confidence": None,
        "influence_source_refs": [],
    }
    fake_conn = FakeConn([row])

    @contextmanager
    def fake_connection() -> Iterator[FakeConn]:
        yield fake_conn

    monkeypatch.setattr(people, "get_connection", fake_connection)
    app = FastAPI()
    app.include_router(people.router)
    client = TestClient(app)

    response = client.get("/people?limit=500")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["limit"] == 250
    assert fake_conn.params[0] == (250,)
    item = body["items"][0]
    assert item["contacts"] == []
    assert item["contactable"] is False
    assert item["person_type"] == "policy_figure"


def test_people_can_filter_by_category_and_mark_operator_people(monkeypatch) -> None:
    row = {
        "id": "person_practitioner",
        "name": "Example Practitioner",
        "roles": ["Public business licence name"],
        "affiliations": [
            {
                "operator_id": "op_practitioner",
                "operator_name": "Example Recovery Studio",
                "organization_name": "Example Recovery Studio",
                "role": "Public business licence name",
            }
        ],
        "public_profiles": {"primary": "https://example.test/practitioner"},
        "primary_category": "recovery_contrast_therapy",
        "categories": ["recovery_contrast_therapy", "spa_thermal"],
        "influence_score": 0.2,
        "locality_score": 1.0,
        "confidence_score": 0.8,
        "source_refs": [SOURCE_REF],
        "last_seen_at": datetime(2026, 6, 22, 12, 0, tzinfo=timezone.utc),
        "influence_components": None,
        "influence_explanation": None,
        "influence_methodology_version": None,
        "influence_source_confidence": None,
        "influence_source_refs": [],
    }
    fake_conn = FakeConn([row])

    @contextmanager
    def fake_connection() -> Iterator[FakeConn]:
        yield fake_conn

    monkeypatch.setattr(people, "get_connection", fake_connection)
    app = FastAPI()
    app.include_router(people.router)
    client = TestClient(app)

    response = client.get("/people?category=recovery_contrast_therapy&limit=10")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["category"] == "recovery_contrast_therapy"
    assert fake_conn.params[0] == ("recovery_contrast_therapy", 10)
    item = body["items"][0]
    assert item["primary_category"] == "recovery_contrast_therapy"
    assert item["categories"] == ["recovery_contrast_therapy", "spa_thermal"]
    assert item["person_type"] == "operator"
