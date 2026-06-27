from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from apps.jobs.analytics.bundles import synthesize_bundles
from apps.jobs.analytics.opportunity import run_opportunity_analytics
from packages.shared.normalizers import infer_service_model, normalize_categories

SOURCE_REF = {
    "source_name": "manual_seed",
    "url": "https://example.test/operator",
    "trust_tier": "informal",
    "seen_at": "2026-06-26T00:00:00Z",
    "source_record_id": "operator",
    "licence": "fixture",
}


def test_p2b_taxonomy_classifies_missing_operator_classes_precisely() -> None:
    quest = normalize_categories("QUEST MEDICAL AESTHETICS", "Medical Aesthetics Clinic")
    cedar = normalize_categories("Cedar Pregnancy Care Centre of Vancouver")
    social = normalize_categories("Sober Social Wellness Cafe and Coworking")
    recovery = normalize_categories("Normatec Compression and Mobility Recovery")

    assert quest == ["aesthetics_medspa"]
    assert "womens_health" in cedar
    assert "social_hospitality" in social
    assert "community_social_wellness" in social
    assert "recovery_modalities" in recovery


def test_service_model_detects_mobile_metro_region() -> None:
    is_mobile, service_area = infer_service_model(
        "Mobile RMT massage",
        "At-home visits across Metro Vancouver",
    )

    assert is_mobile is True
    assert service_area is not None
    assert service_area["type"] == "metro_region"
    assert "Vancouver" in service_area["municipalities"]


def test_new_p2b_bundles_and_blended_memberships_are_synthesized() -> None:
    now = datetime(2026, 6, 26, 12, 0, tzinfo=timezone.utc)
    operators = [
        _operator("op_quest", "QUEST MEDICAL AESTHETICS", ["aesthetics_medspa"]),
        _operator("op_cedar", "Cedar Pregnancy Care", ["womens_health"]),
        _operator("op_recover", "Recover Lab Normatec Mobility", ["recovery_modalities"]),
        _operator(
            "op_social",
            "Sober Social Wellness Cafe",
            ["social_hospitality", "community_social_wellness"],
        ),
    ]

    bundles = synthesize_bundles(
        operators=operators,
        geographies=[_csd("5915022", "Vancouver", 662248)],
        signals=[],
        people=[],
        now=now,
    )
    labels = {bundle["label"] for bundle in bundles}
    social = next(bundle for bundle in bundles if bundle["label"] == "Social hospitality wellness")

    assert "Aesthetics & med-spa" in labels
    assert "Women's health & postnatal" in labels
    assert "Recovery modalities" in labels
    assert "Social hospitality wellness" in labels
    assert social["memberships"][0]["operator_id"] == "op_social"


def test_mobile_service_area_counts_neighborhood_supply() -> None:
    repo = FakeP2BOpportunityRepo()

    run_opportunity_analytics(repo)  # type: ignore[arg-type]

    downtown_spa = next(
        cell
        for cell in repo.heatmap_cells
        if cell["category"] == "spa_thermal"
        and cell["geo_level"] == "neighborhood"
        and cell["geo_name"] == "Downtown"
    )
    inputs = downtown_spa["trace_payload"]

    assert downtown_spa["supply_count"] == 1
    assert inputs["mobile_operator_ids"] == ["op_mobile_massage"]
    assert inputs["service_area_supply_count"] == 1


class FakeP2BOpportunityRepo:
    def __init__(self) -> None:
        self.operators = [
            _operator(
                "op_mobile_massage",
                "Metro Mobile Massage",
                ["spa_thermal"],
                municipality=None,
                neighborhood=None,
                lat=None,
                lng=None,
                is_mobile=True,
                service_area={
                    "type": "metro_region",
                    "municipalities": ["Vancouver"],
                    "methodology_version": "test",
                },
            ),
            _operator(
                "op_context",
                "Downtown Context Gym",
                ["fitness_movement"],
                municipality="Vancouver",
                neighborhood="Downtown",
            ),
        ]
        self.heatmap_cells: list[dict[str, Any]] = []
        self.scorecards: list[dict[str, Any]] = []
        self.velocities: dict[tuple[str, int], dict[str, Any]] = {}
        self.taxonomy_specs: list[str] = []

    def categories_with_denominators(self) -> list[str]:
        return []

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
        return [_csd("5915022", "Vancouver", 100000)]

    def population_ceiling(self) -> float:
        return 100000

    def operators_with_neighborhoods(self) -> list[dict[str, Any]]:
        return [operator for operator in self.operators if operator.get("neighborhood")]

    def operators_for_category(self, category: str) -> list[dict[str, Any]]:
        return [
            operator
            for operator in self.operators
            if category in operator.get("categories", [])
        ]

    def business_denominator(self, geo_code: str, category: str) -> dict[str, Any] | None:
        return None

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


def _operator(
    operator_id: str,
    name: str,
    categories: list[str],
    *,
    municipality: str | None = "Vancouver",
    neighborhood: str | None = "Downtown",
    lat: float | None = 49.28,
    lng: float | None = -123.12,
    is_mobile: bool = False,
    service_area: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": operator_id,
        "name": name,
        "normalized_name": name.lower(),
        "organization_id": None,
        "organization_name": None,
        "categories": categories,
        "venue_class": "commercial_wellness",
        "address": "123 Example Street, Vancouver, BC" if lat is not None else None,
        "municipality": municipality,
        "neighborhood": neighborhood,
        "lat": lat,
        "lng": lng,
        "is_mobile": is_mobile,
        "service_area": service_area,
        "first_seen_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
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
