from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.app.routers import propositions


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


SOURCE_REF = {
    "source_name": "statcan_wds",
    "url": "https://www.statcan.gc.ca/en/developers/wds",
    "trust_tier": "official",
    "seen_at": "2026-06-18T00:00:00Z",
    "source_record_id": "wds",
    "licence": "Statistics Canada terms",
}


def test_propositions_endpoint_returns_written_evidence(monkeypatch) -> None:
    row = {
        "id": "prop_recovery_mount_pleasant",
        "heatmap_cell_id": "heat_recovery_mount_pleasant",
        "category": "recovery_contrast_therapy",
        "geo_code": "nh_5915022_mount_pleasant",
        "geo_name": "Mount Pleasant",
        "geo_level": "neighborhood",
        "municipality": "Vancouver",
        "headline": "Open recovery and contrast therapy in Mount Pleasant",
        "summary": "Open recovery and contrast therapy in Mount Pleasant: sourced evidence.",
        "competitor_count_within_radius": 3,
        "competitor_radius_km": 4.0,
        "population": 44149.8667,
        "business_count": 17.3333,
        "demand_source": "statcan_wds_fixture",
        "supporting_signals": [
            {"kind": "population", "label": "44,150 people", "source_refs": [SOURCE_REF]}
        ],
        "component_breakdown": {"inputs": {"demand_source_status": "fixture_fallback"}},
        "opportunity_score": 0.78,
        "confidence_score": 0.63,
        "source_refs": [SOURCE_REF],
        "generated_at": datetime(2026, 6, 22, 12, 0, tzinfo=timezone.utc),
    }
    fake_conn = FakeConn([row])

    @contextmanager
    def fake_connection() -> Iterator[FakeConn]:
        yield fake_conn

    monkeypatch.setattr(propositions, "get_connection", fake_connection)
    app = FastAPI()
    app.include_router(propositions.router)
    client = TestClient(app)

    response = client.get(
        "/propositions?category=recovery_contrast_therapy&geo_level=neighborhood"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["count"] == 1
    item = body["items"][0]
    assert item["headline"] == row["headline"]
    assert item["confidence"] == 0.63
    assert item["source_refs"] == [SOURCE_REF]
    assert item["supporting_signals"][0]["kind"] == "population"
    assert "prop.geo_level = %s" in fake_conn.queries[0][0]
