from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from apps.jobs.analytics.opportunity import run_opportunity_analytics

SOURCE_REF = {
    "source_name": "manual_seed",
    "url": "https://example.test/operator",
    "trust_tier": "informal",
    "seen_at": "2026-06-26T00:00:00Z",
    "source_record_id": "operator",
    "licence": "fixture",
}


class FakeP1AOpportunityRepo:
    def __init__(self) -> None:
        self.operators = [
            _operator(
                "op_aetherhaus",
                "AetherHaus Sauna",
                ["recovery_contrast_therapy"],
                "Vancouver",
                "West End",
            ),
            _operator(
                "op_strength",
                "Iron Lab Strength",
                ["fitness_movement"],
                "Vancouver",
                "Downtown",
            ),
            _operator(
                "op_physio",
                "Downtown Physio",
                ["allied_health"],
                "Vancouver",
                "Downtown",
            ),
            _operator(
                "op_yoga",
                "Kitsilano Yoga Pilates",
                [],
                "Vancouver",
                "Kitsilano",
            ),
            _operator(
                "op_spa",
                "Steam and Sauna Spa",
                ["spa_thermal"],
                "Burnaby",
                "Brentwood",
                first_seen_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            ),
        ]
        self.heatmap_cells: list[dict[str, Any]] = []
        self.scorecards: list[dict[str, Any]] = []
        self.velocities: dict[tuple[str, int], dict[str, Any]] = {}
        self.taxonomy_specs: list[str] = []

    def categories_with_denominators(self) -> list[str]:
        return ["recovery_contrast_therapy"]

    def operator_categories(self) -> list[str]:
        return sorted(
            {
                category
                for operator in self.operators
                for category in operator.get("categories", [])
            }
        )

    def operators_for_opportunity_matching(self) -> list[dict[str, Any]]:
        return self.operators

    def upsert_category_taxonomy(self, spec: Any) -> None:
        self.taxonomy_specs.append(spec.key)

    def geographies(self) -> list[dict[str, Any]]:
        return [_csd("5915022", "Vancouver", 100000), _csd("5915025", "Burnaby", 50000)]

    def population_ceiling(self) -> float:
        return 100000

    def operators_with_neighborhoods(self) -> list[dict[str, Any]]:
        return self.operators

    def operators_for_category(self, category: str) -> list[dict[str, Any]]:
        return [
            operator
            for operator in self.operators
            if category in operator.get("categories", [])
        ]

    def business_denominator(self, geo_code: str, category: str) -> dict[str, Any] | None:
        if category != "recovery_contrast_therapy":
            return None
        return {
            "id": f"den_{geo_code}_{category}",
            "value": 100.0,
            "source_refs": [SOURCE_REF],
            "confidence_score": 0.9,
            "payload": {"demand_source_status": "fixture"},
        }

    def upsert_neighborhood_geography(self, payload: dict[str, Any]) -> bool:
        return True

    def signal_count_for_geo_category(
        self, geo_name: str, category: str, days: int
    ) -> tuple[int, list[dict[str, Any]], list[float]]:
        return 0, [], []

    def velocity_refs_and_counts_for_operator_set(
        self,
        category: str,
        days: int,
        operators: list[dict[str, Any]],
    ) -> tuple[dict[str, int], list[dict[str, Any]], float]:
        cutoff = datetime(2026, 6, 26, tzinfo=timezone.utc)
        recent = [
            operator
            for operator in operators
            if operator["first_seen_at"] >= cutoff - timedelta(days=days)
        ]
        counts = {
            "new_operator_count": len(recent),
            "job_velocity_count": 0,
            "event_velocity_count": 0,
            "news_velocity_count": 0,
        }
        return counts, [], 0.5

    def upsert_heatmap_cell(self, payload: dict[str, Any]) -> None:
        self.heatmap_cells.append(payload)

    def upsert_scorecard(self, payload: dict[str, Any]) -> None:
        self.scorecards.append(payload)

    def upsert_velocity(
        self,
        category: str,
        days: int,
        counts: dict[str, int],
        refs: list[dict[str, Any]],
        confidence: float,
    ) -> None:
        self.velocities[(category, days)] = {
            "counts": counts,
            "refs": refs,
            "confidence": confidence,
        }

    def close(self) -> None:
        return None


def test_opportunity_analytics_scores_operator_and_bundle_categories() -> None:
    repo = FakeP1AOpportunityRepo()

    run_opportunity_analytics(repo)  # type: ignore[arg-type]

    heatmap_categories = {cell["category"] for cell in repo.heatmap_cells}
    scorecard_categories = {card["category"] for card in repo.scorecards}
    required = {"fitness_movement", "allied_health", "yoga_pilates"}

    assert len(heatmap_categories) >= 3
    assert required <= heatmap_categories
    assert required <= scorecard_categories
    assert "yoga_pilates" in repo.taxonomy_specs

    fitness_vancouver = next(
        cell
        for cell in repo.heatmap_cells
        if cell["category"] == "fitness_movement" and cell["geo_name"] == "Vancouver"
    )
    assert fitness_vancouver["supply_count"] == 1
    assert fitness_vancouver["trace_payload"]["demand_source_status"] == (
        "operator_observed_fallback"
    )
    assert fitness_vancouver["source_refs"]


def test_category_velocity_writes_zero_counts_for_populated_quiet_category() -> None:
    repo = FakeP1AOpportunityRepo()

    run_opportunity_analytics(repo)  # type: ignore[arg-type]

    spa_velocity = repo.velocities[("spa_thermal", 30)]["counts"]
    assert spa_velocity["new_operator_count"] == 0
    assert isinstance(spa_velocity["new_operator_count"], int)


def _operator(
    operator_id: str,
    name: str,
    categories: list[str],
    municipality: str,
    neighborhood: str,
    *,
    first_seen_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "id": operator_id,
        "name": name,
        "normalized_name": name.lower(),
        "organization_id": None,
        "organization_name": None,
        "categories": categories,
        "venue_class": "commercial_wellness",
        "address": f"123 {neighborhood} Street, {municipality}, BC",
        "municipality": municipality,
        "neighborhood": neighborhood,
        "lat": 49.28,
        "lng": -123.12,
        "first_seen_at": first_seen_at or datetime(2026, 6, 1, tzinfo=timezone.utc),
        "is_new_180d": True,
        "source_refs": [{**SOURCE_REF, "source_record_id": operator_id}],
        "confidence_score": 0.9,
        "raw_payloads": [],
    }


def _csd(geo_code: str, name: str, population: float) -> dict[str, Any]:
    return {
        "geo_code": geo_code,
        "geo_level": "CSD",
        "geo_name": name,
        "parent_geo_code": None,
        "municipality": name,
        "lat": 49.25,
        "lng": -123.1,
        "geography_source_refs": [SOURCE_REF],
        "geography_confidence": 0.95,
        "geography_payload": {},
        "population_denominator_id": f"den_{geo_code}_population",
        "population": population,
        "population_source_refs": [SOURCE_REF],
        "population_confidence": 0.9,
        "population_payload": {"demand_source_status": "fixture"},
    }
