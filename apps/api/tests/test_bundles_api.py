from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.app.routers import bundles

SOURCE_REF = {
    "source_name": "bundle_synthesis_taxonomy",
    "url": "apps/jobs/analytics/bundles.py",
    "trust_tier": "informal",
    "seen_at": "2026-06-22T00:00:00Z",
    "source_record_id": "r1_bundle_synthesis_v1",
    "licence": None,
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


def test_bundles_list_is_ranked_and_filterable(monkeypatch) -> None:
    fake_conn = FakeConn([[_bundle_row()]])

    @contextmanager
    def fake_connection() -> Iterator[FakeConn]:
        yield fake_conn

    monkeypatch.setattr(bundles, "get_connection", fake_connection)
    app = FastAPI()
    app.include_router(bundles.router)
    client = TestClient(app)

    response = client.get("/bundles?municipality=Vancouver&geo_level=neighborhood&limit=500")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["limit"] == 100
    assert body["items"][0]["label"] == "Cold plunge & contrast therapy"
    query, params = fake_conn.queries[0]
    assert "ORDER BY b.bundle_score DESC" in query
    assert params == ["Vancouver", "Vancouver", "neighborhood", 100]


def test_bundle_detail_returns_members_and_top_people(monkeypatch) -> None:
    fake_conn = FakeConn(
        [
            [_bundle_row()],
            [_member_row()],
            [_person_row()],
            [_worldwide_row()],
            [
                _first_mover_city_row("Austin", 9, 9.235, 1.224),
                _first_mover_city_row("Vancouver", 5, 7.55, 1.0),
            ],
        ]
    )

    @contextmanager
    def fake_connection() -> Iterator[FakeConn]:
        yield fake_conn

    monkeypatch.setattr(bundles, "get_connection", fake_connection)
    app = FastAPI()
    app.include_router(bundles.router)
    client = TestClient(app)

    response = client.get("/bundles/bundle_cold_plunge_contrast_therapy")

    assert response.status_code == 200
    body = response.json()
    assert body["members"][0]["name"] == "AetherHaus"
    assert body["members"][0]["lat"] == 49.2869
    assert body["members"][0]["contacts"][0]["contact_type"] == "website"
    assert body["top_people"][0]["why_appears"].startswith("Founder at AetherHaus")
    assert body["supporting_signals"][0]["source_refs"] == [SOURCE_REF]
    assert body["worldwide_match"]["verdict"] == "global wave"
    assert body["worldwide_match"]["source_status"] == "live"
    assert body["worldwide_match"]["source_refs"]
    assert body["first_mover_cities"][0]["city"] == "Austin"
    assert body["first_mover_cities"][0]["ratio_vs_vancouver"] == 1.224
    assert body["first_mover_cities"][0]["source_refs"]


def _bundle_row() -> dict[str, Any]:
    generated_at = datetime(2026, 6, 22, 12, 0, tzinfo=timezone.utc)
    return {
        "id": "bundle_cold_plunge_contrast_therapy",
        "label": "Cold plunge & contrast therapy",
        "slug": "cold-plunge-contrast-therapy",
        "bundle_score": 0.74,
        "components": {"demand_proxy": 0.9, "formula": "formula"},
        "geography": {
            "concentrations": [
                {
                    "geo_level": "neighborhood",
                    "geo_name": "Mount Pleasant",
                    "municipality": "Vancouver",
                    "member_count": 2,
                    "source_refs": [SOURCE_REF],
                }
            ],
            "municipalities": [{"geo_name": "Vancouver", "member_count": 2}],
        },
        "member_count": 2,
        "supporting_signals": [
            {
                "id": "sig_a",
                "title": "AetherHaus observed",
                "source_refs": [SOURCE_REF],
            }
        ],
        "source_refs": [SOURCE_REF],
        "confidence_score": 0.82,
        "generated_at": generated_at,
    }


def _member_row() -> dict[str, Any]:
    return {
        "id": "op_aetherhaus",
        "name": "AetherHaus",
        "categories": ["recovery_contrast_therapy"],
        "status": "open",
        "address": "1768 Davie Street, Vancouver, BC",
        "municipality": "Vancouver",
        "neighborhood": "West End",
        "phone": None,
        "website": "https://www.aetherhaus.ca/",
        "social_links": {},
        "organization_id": None,
        "orgbook_id": None,
        "lat": 49.2869,
        "lng": -123.1416,
        "confidence_score": 0.92,
        "source_refs": [SOURCE_REF],
        "last_seen_at": datetime(2026, 6, 22, 12, 0, tzinfo=timezone.utc),
        "match_reasons": {"category_matches": ["recovery_contrast_therapy"]},
        "membership_source_refs": [SOURCE_REF],
        "membership_confidence_score": 0.95,
        "contacts": [
            {
                "type": "website",
                "contact_type": "website",
                "value": "https://www.aetherhaus.ca/",
                "platform": None,
                "source_ref": SOURCE_REF,
                "confidence": 0.9,
            }
        ],
    }


def _person_row() -> dict[str, Any]:
    return {
        "id": "person_a",
        "name": "A Public Founder",
        "roles": ["Founder"],
        "affiliations": [{"organization_name": "AetherHaus", "role": "Founder"}],
        "public_profiles": {"primary": "https://example.test/person"},
        "rank": 1,
        "influence_score": 0.82,
        "why_appears": "Founder at AetherHaus links this person to Cold plunge.",
        "source_refs": [SOURCE_REF],
        "confidence_score": 0.9,
        "last_seen_at": datetime(2026, 6, 22, 12, 0, tzinfo=timezone.utc),
    }


def _worldwide_row() -> dict[str, Any]:
    return {
        "worldwide_match": {
            "direction": "rising",
            "value": 0.18,
            "verdict": "global wave",
            "source_status": "live",
            "confidence_score": 0.7,
            "window_days": 90,
            "methodology_version": "r3_bundle_global_signal_v1",
            "components": {"cities_with_supply": 6},
            "source_errors": [],
            "source_refs": [
                {
                    "source_name": "gdelt_doc",
                    "url": "https://api.gdeltproject.org/api/v2/doc/doc",
                    "trust_tier": "community",
                    "seen_at": "2026-06-22T00:00:00Z",
                    "source_record_id": "gdelt_cold",
                    "licence": "GDELT Project terms",
                }
            ],
        },
        "source_refs": [
            {
                "source_name": "gdelt_doc",
                "url": "https://api.gdeltproject.org/api/v2/doc/doc",
                "trust_tier": "community",
                "seen_at": "2026-06-22T00:00:00Z",
                "source_record_id": "gdelt_cold",
                "licence": "GDELT Project terms",
            }
        ],
    }


def _first_mover_city_row(
    city: str,
    count: int,
    density: float,
    ratio_vs_vancouver: float,
) -> dict[str, Any]:
    return {
        "city": city,
        "count": count,
        "density": density,
        "ratio_vs_vancouver": ratio_vs_vancouver,
        "source_status": "live",
        "confidence_score": 0.74,
        "source_error": None,
        "source_refs": [
            {
                "source_name": "osm_overpass_first_mover",
                "url": "https://overpass-api.de/api/interpreter",
                "trust_tier": "community",
                "seen_at": "2026-06-22T00:00:00Z",
                "source_record_id": f"osm_{city}",
                "licence": "Open Database License",
            }
        ],
    }
