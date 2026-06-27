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


def test_opportunity_scorecards_can_retarget_demographic_fit(monkeypatch) -> None:
    row = {
        "id": "score_marpole_womens",
        "category": "womens_health",
        "geo_code": "nh_marpole",
        "geo_name": "Marpole",
        "geo_level": "neighborhood",
        "opportunity_score": 0.5,
        "component_breakdown": {
            "category": "womens_health",
            "geo_name": "Marpole",
            "demand_proxy": 0.7,
            "low_supply_density": 1.0,
            "category_growth": 0.0,
            "target_demo_fit": 0.5,
            "transit_access": 0.8,
            "event_community_activity": 0.0,
            "source_confidence": 0.9,
            "target_demo_fit_components": {
                "target_demo": "young_families",
                "source_status": "official_neighborhood_demographics",
            },
            "inputs": {
                "category": "womens_health",
                "geo_name": "Marpole",
                "base_population_demand": 0.7,
                "business_density_normalized": 0.25,
            },
        },
        "source_refs": [SOURCE_REF],
        "confidence_score": 0.8,
        "calculation_method": "formula",
        "caveat": "test",
        "generated_at": datetime(2026, 6, 26, 12, 0, tzinfo=timezone.utc),
    }
    fake_conn = FakeConn([row])

    @contextmanager
    def fake_connection() -> Iterator[FakeConn]:
        yield fake_conn

    monkeypatch.setattr(analytics, "get_connection", fake_connection)
    app = FastAPI()
    app.include_router(analytics.router)
    client = TestClient(app)

    response = client.get(
        "/analytics/opportunity-scorecards"
        "?category=womens_health&target_demo=affluent_35_55"
    )

    assert response.status_code == 200
    body = response.json()
    item = body["items"][0]
    fit = item["component_breakdown"]["target_demo_fit_components"]
    assert body["meta"]["target_demo"] == "affluent_35_55"
    assert fit["target_demo"] == "affluent_35_55"
    assert item["component_breakdown"]["target_demo_fit"] != 0.5
    assert "Retargeted target_demo=affluent_35_55" in item["calculation_method"]


def test_proximity_endpoint_scores_colocation(monkeypatch) -> None:
    row = {
        "id": "op_recover",
        "name": "Recover Lab Mobility",
        "categories": ["recovery_modalities"],
        "municipality": "Vancouver",
        "neighborhood": "Mount Pleasant",
        "lat": 49.267,
        "lng": -123.1,
        "source_refs": [SOURCE_REF],
        "confidence_score": 0.84,
        "nearby_count": 1,
        "min_distance_km": 0.25,
        "nearby_operators": [
            {
                "operator_id": "op_strength",
                "name": "Iron Lab Strength",
                "categories": ["fitness_movement"],
                "municipality": "Vancouver",
                "neighborhood": "Mount Pleasant",
                "distance_km": 0.25,
                "source_refs": [SOURCE_REF],
                "confidence_score": 0.9,
            }
        ],
    }
    fake_conn = FakeConn([row])

    @contextmanager
    def fake_connection() -> Iterator[FakeConn]:
        yield fake_conn

    monkeypatch.setattr(analytics, "get_connection", fake_connection)
    app = FastAPI()
    app.include_router(analytics.router)
    client = TestClient(app)

    response = client.get(
        "/analytics/proximity?category=recovery_modalities"
        "&near_category=fitness_movement&radius_km=1"
    )

    assert response.status_code == 200
    body = response.json()
    item = body["items"][0]
    assert item["operator_id"] == "op_recover"
    assert item["near_category"] == "fitness_movement"
    assert item["nearby_operators"][0]["name"] == "Iron Lab Strength"
    assert item["proximity_score"] == 0.75
    assert item["source_refs"]
    query, params = fake_conn.queries[0]
    assert "ST_DWithin(subject.geom, ref.geom" in query
    assert params == ["recovery_modalities", "fitness_movement", 1000.0, 100]
