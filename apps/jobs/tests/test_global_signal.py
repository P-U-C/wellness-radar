from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from apps.jobs.analytics.global_signal import (
    GDELT_SOURCE_NAME,
    OSM_SOURCE_NAME,
    InMemoryBundleGlobalRepository,
    run_bundle_global_signal,
)

SOURCE_REF = {
    "source_name": "bundle_synthesis_taxonomy",
    "url": "apps/jobs/analytics/bundles.py",
    "trust_tier": "informal",
    "seen_at": "2026-06-22T00:00:00Z",
    "source_record_id": "r1_bundle_synthesis_v1",
    "licence": None,
}


def test_bundle_global_signal_uses_live_responses_without_operator_writes() -> None:
    repository = InMemoryBundleGlobalRepository([_bundle_row()])
    client = FakeGlobalSignalClient()

    metrics = run_bundle_global_signal(
        repository,
        client=client,
        now=datetime(2026, 6, 22, 12, 0, tzinfo=timezone.utc),
        gdelt_rate_limit_seconds=0,
    )

    record = repository.global_records["bundle_cold_plunge_contrast_therapy"]
    assert metrics.records_fetched == 8
    assert metrics.records_persisted == 8
    assert record.worldwide_match["direction"] == "rising"
    assert record.worldwide_match["verdict"] == "global wave"
    assert record.worldwide_match["source_status"] == "live"
    assert record.worldwide_match["source_refs"]
    austin = next(city for city in record.first_mover_cities if city.city == "Austin")
    assert austin.ratio_vs_vancouver > 1
    assert all(city.source_refs for city in record.first_mover_cities)
    assert all(city.source_status == "live" for city in record.first_mover_cities)
    assert not hasattr(repository, "operators")
    assert GDELT_SOURCE_NAME in {run["source_name"] for run in repository.source_runs.values()}
    assert OSM_SOURCE_NAME in {run["source_name"] for run in repository.source_runs.values()}
    assert 'nwr["leisure"="sauna"]' in client.overpass_queries[0]
    assert '"cold plunge"' in str(client.gdelt_params[0]["query"])


def test_bundle_global_signal_fixture_fallback_is_labeled_and_lower_confidence() -> None:
    repository = InMemoryBundleGlobalRepository([_bundle_row()])

    metrics = run_bundle_global_signal(
        repository,
        client=FailingGlobalSignalClient(),
        now=datetime(2026, 6, 22, 12, 0, tzinfo=timezone.utc),
        gdelt_rate_limit_seconds=0,
    )

    record = repository.global_records["bundle_cold_plunge_contrast_therapy"]
    assert metrics.records_persisted == 8
    assert record.worldwide_match["source_status"] == "fixture_fallback"
    assert record.worldwide_match["confidence_score"] < 0.5
    assert record.worldwide_match["source_errors"]
    assert all(city.source_status == "fixture_fallback" for city in record.first_mover_cities)
    assert all(city.source_error for city in record.first_mover_cities)
    assert any(
        raw.get("source_status") == "fixture_fallback" and raw.get("live_error")
        for raw in repository.raw_payloads.values()
    )


class FakeResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self) -> dict[str, Any]:
        return self.payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}: {self.text}")


class FakeGlobalSignalClient:
    def __init__(self) -> None:
        self.gdelt_params: list[dict[str, Any]] = []
        self.overpass_queries: list[str] = []
        self.counts = [5, 9, 80, 50, 100, 40, 25]

    def get(self, url: str, params: dict[str, Any]) -> FakeResponse:
        self.gdelt_params.append(params)
        return FakeResponse(
            {
                "timeline": [
                    {
                        "series": "Volume Intensity",
                        "data": [
                            {"date": "20260401T000000Z", "value": 0.05},
                            {"date": "20260415T000000Z", "value": 0.06},
                            {"date": "20260501T000000Z", "value": 0.08},
                            {"date": "20260515T000000Z", "value": 0.11},
                            {"date": "20260601T000000Z", "value": 0.15},
                            {"date": "20260615T000000Z", "value": 0.19},
                        ],
                    }
                ]
            }
        )

    def post(self, url: str, data: dict[str, Any]) -> FakeResponse:
        self.overpass_queries.append(str(data["data"]))
        count = self.counts[len(self.overpass_queries) - 1]
        return FakeResponse(
            {
                "elements": [
                    {
                        "type": "count",
                        "id": 0,
                        "tags": {
                            "nodes": str(count),
                            "ways": "0",
                            "relations": "0",
                            "areas": "0",
                            "total": str(count),
                        },
                    }
                ]
            }
        )


class FailingGlobalSignalClient:
    def get(self, url: str, params: dict[str, Any]) -> FakeResponse:
        raise RuntimeError("GDELT unavailable")

    def post(self, url: str, data: dict[str, Any]) -> FakeResponse:
        raise RuntimeError("Overpass unavailable")


def _bundle_row() -> dict[str, Any]:
    return {
        "id": "bundle_cold_plunge_contrast_therapy",
        "label": "Cold plunge & contrast therapy",
        "slug": "cold-plunge-contrast-therapy",
        "source_refs": [SOURCE_REF],
    }
