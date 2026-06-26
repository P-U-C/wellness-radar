from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from apps.jobs.analytics.bundles import synthesize_bundles
from apps.jobs.analytics.opportunity import (
    _neighborhood_denominator_context,
    _neighborhood_rows_for_category,
    _payload_for_cell,
)
from apps.jobs.analytics.scoring import dedupe_operators, supply_sparsity_score
from packages.shared.normalizers import normalize_categories

SOURCE_REF = {
    "source_name": "manual_seed",
    "url": "https://example.test/operator",
    "trust_tier": "informal",
    "seen_at": "2026-06-26T00:00:00Z",
    "source_record_id": "operator",
    "licence": "fixture",
}


class FakeOpportunityRepo:
    def __init__(self) -> None:
        self.upserted_geographies: list[dict[str, Any]] = []

    def business_denominator(self, geo_code: str, category: str) -> dict[str, Any]:
        return {
            "id": f"den_{geo_code}_{category}",
            "value": 100.0,
            "source_refs": [SOURCE_REF],
            "confidence_score": 0.9,
            "payload": {"demand_source_status": "fixture"},
        }

    def upsert_neighborhood_geography(self, payload: dict[str, Any]) -> bool:
        self.upserted_geographies.append(payload)
        return True

    def signal_count_for_geo_category(
        self, geo_name: str, category: str, days: int
    ) -> tuple[int, list[dict[str, Any]], list[float]]:
        return 0, [], []


def test_neighborhood_population_uses_local_area_and_correct_municipality() -> None:
    operators = [
        _operator("op_downtown", "Downtown Recovery", "Vancouver", "Downtown"),
        _operator("op_marpole", "Marpole Recovery", "Richmond", "Marpole"),
    ]
    repo = FakeOpportunityRepo()

    rows = _neighborhood_rows_for_category(
        repo=repo,  # type: ignore[arg-type]
        category="recovery_contrast_therapy",
        category_operators=operators,
        csd_geographies=[_csd("5915022", "Vancouver", 662248), _csd("5915015", "Richmond", 209937)],
        neighborhood_context=_neighborhood_denominator_context(operators),
    )

    by_name = {row["geo"]["geo_name"]: row for row in rows}
    downtown = by_name["Downtown"]
    marpole = by_name["Marpole"]

    assert downtown["geo"]["population"] == 62030
    assert downtown["geo"]["population"] < 100000
    assert downtown["geo"]["population_payload"]["population_estimation_status"] == (
        "official_neighborhood"
    )
    assert marpole["geo"]["municipality"] == "Vancouver"
    assert marpole["geo"]["parent_geo_code"] == "5915022"
    assert marpole["geo"]["population"] == 24460
    assert all(item["municipality"] == "Vancouver" for item in repo.upserted_geographies)


def test_unknown_neighborhood_population_estimate_is_capped_not_whole_csd() -> None:
    operator = _operator("op_brentwood", "Brentwood Fitness", "Burnaby", "Brentwood")
    repo = FakeOpportunityRepo()

    rows = _neighborhood_rows_for_category(
        repo=repo,  # type: ignore[arg-type]
        category="fitness_movement",
        category_operators=[operator],
        csd_geographies=[_csd("5915025", "Burnaby", 249125)],
        neighborhood_context=_neighborhood_denominator_context([operator]),
    )

    row = rows[0]
    assert row["geo"]["population"] == 62281.25
    assert row["geo"]["population_payload"]["population_allocation_share"] == 0.25
    assert row["geo"]["population_payload"]["population_estimation_status"] == "estimated"


def test_operator_dedupe_collapses_known_duplicate_patterns() -> None:
    operators = [
        _operator("oxygen_a", "Oxygen Yoga & Fitness", "Vancouver", "Kitsilano", lat=49.27),
        _operator("oxygen_b", "Oxygen Yoga & Fitness", "Vancouver", "Kitsilano", lat=49.2704),
        _operator("oxygen_c", "Oxygen Yoga & Fitness", "Vancouver", "Kitsilano", lat=49.2705),
        _operator("club_a", "Club Pilates", "Vancouver", "Downtown", lat=49.28, lng=-123.12),
        _operator("club_b", "Club Pilates", "Vancouver", "Downtown", lat=49.2803, lng=-123.1202),
        _operator("lagree_a", "Lagree West", "Vancouver", "Kitsilano", lat=49.264),
        _operator("lagree_b", "Lagree West", "Vancouver", "Kitsilano", lat=49.2641),
        _operator(
            "oxygen_other",
            "Oxygen Yoga & Fitness",
            "Burnaby",
            "Brentwood",
            lat=49.25,
            address="456 Different Street, Burnaby, BC",
        ),
    ]

    deduped = dedupe_operators(operators)
    by_name: dict[str, list[dict[str, Any]]] = {}
    for operator in deduped:
        by_name.setdefault(operator["name"], []).append(operator)

    assert len(by_name["Oxygen Yoga & Fitness"]) == 2
    assert by_name["Club Pilates"][0]["dedupe_cluster_size"] == 2
    assert by_name["Lagree West"][0]["dedupe_cluster_size"] == 2


def test_yoga_pilates_density_no_longer_scores_as_under_supplied() -> None:
    operators = [
        _operator(
            f"yoga_{index}",
            f"Yoga Studio {index}",
            "Vancouver",
            "Downtown",
            categories=[],
            lat=49.28 + index * 0.0001,
        )
        for index in range(15)
    ]

    bundles = synthesize_bundles(
        operators=operators,
        geographies=[_csd("5915022", "Vancouver", 100000)],
        signals=[],
        people=[],
        now=datetime(2026, 6, 26, tzinfo=timezone.utc),
    )

    yoga = next(bundle for bundle in bundles if bundle["label"] == "Yoga & pilates")
    assert yoga["components"]["inputs"]["bundle_density_per_10000_population"] == 1.5
    assert yoga["components"]["low_supply_density"] == 0.0
    assert supply_sparsity_score(3.0) == 0.0


def test_payload_low_supply_uses_absolute_per_capita_saturation() -> None:
    payload = _payload_for_cell(
        category="fitness_movement",
        row={
            "geo": _csd("5915022", "Vancouver", 100000),
            "denominator": {
                "id": "den_business",
                "value": 200,
                "source_refs": [SOURCE_REF],
                "confidence_score": 0.9,
            },
            "operators": [
                _operator(f"op_{index}", f"Gym {index}", "Vancouver", "Downtown")
                for index in range(20)
            ],
            "signal_count": 0,
            "signal_refs": [],
            "signal_conf": [],
            "density": 2.0,
            "business_density": 20.0,
            "new_operators": 0,
            "nearest_competitors": [],
        },
        max_population=100000,
        max_business_density=20,
        max_activity=1,
        max_growth=1,
    )

    assert payload["components"]["low_supply_density"] == 0.0


def test_bundle_hygiene_removes_named_bad_members_and_keeps_legitimate_members() -> None:
    operators = [
        _operator(
            "op_aetherhaus",
            "AetherHaus",
            "Vancouver",
            "Downtown",
            categories=["recovery_contrast_therapy", "spa_thermal"],
            raw_payloads=[{"tags": {"leisure": "sauna", "amenity": "spa"}}],
        ),
        _operator(
            "op_rehab",
            "Together We Can Drug & Alcohol Recovery",
            "Vancouver",
            "Mount Pleasant",
            categories=["recovery_contrast_therapy"],
        ),
        _operator(
            "op_road",
            "Coast Mental Health - Road to Recovery",
            "Vancouver",
            "Downtown",
            categories=["recovery_contrast_therapy", "mental_health"],
        ),
        _operator(
            "op_iv",
            "Longevity IV Lounge",
            "Vancouver",
            "Downtown",
            categories=["nutrition_longevity"],
        ),
        _operator(
            "op_crag",
            "Cougar Crag",
            "Vancouver",
            "Downtown",
            categories=["nutrition_longevity"],
        ),
        _operator(
            "op_tower",
            "Tombstone Tower",
            "Vancouver",
            "Downtown",
            categories=["nutrition_longevity"],
        ),
        _operator(
            "op_poison",
            "Well of Poison Area",
            "Vancouver",
            "Downtown",
            categories=["nutrition_longevity"],
        ),
        _operator(
            "op_knuckle",
            "Knuckle Head",
            "Vancouver",
            "Downtown",
            categories=["nutrition_longevity"],
        ),
        _operator(
            "op_nails",
            "Milano Nail Spa",
            "Vancouver",
            "Downtown",
            categories=["spa_thermal"],
        ),
        _operator(
            "op_space",
            "Third Space Counselling",
            "Vancouver",
            "Downtown",
            categories=["spa_thermal"],
        ),
        _operator(
            "op_contractor",
            "THIRD SPACE CONTRACTING LTD",
            "Vancouver",
            "Downtown",
            categories=["spa_thermal"],
        ),
        _operator(
            "op_sauna",
            "Steam & Sauna Spa",
            "Vancouver",
            "Downtown",
            categories=["spa_thermal"],
        ),
        _operator(
            "op_strength",
            "Iron Lab Strength",
            "Vancouver",
            "Downtown",
            categories=["fitness_movement"],
        ),
        _operator(
            "op_martial",
            "Dragon Temple Martial Arts",
            "Vancouver",
            "Downtown",
            categories=["fitness_movement"],
        ),
    ]

    bundles = synthesize_bundles(
        operators=operators,
        geographies=[_csd("5915022", "Vancouver", 662248)],
        signals=[],
        people=[],
        now=datetime(2026, 6, 26, tzinfo=timezone.utc),
    )

    cold_names = _bundle_member_names(bundles, "Cold plunge & contrast therapy")
    longevity_names = _bundle_member_names(bundles, "Longevity / IV")
    spa_names = _bundle_member_names(bundles, "Spa & thermal")
    strength_names = _bundle_member_names(bundles, "Boutique strength")

    assert "AetherHaus" in cold_names
    assert "Together We Can Drug & Alcohol Recovery" not in cold_names
    assert "Coast Mental Health - Road to Recovery" not in cold_names
    assert "Longevity IV Lounge" in longevity_names
    assert {"Cougar Crag", "Tombstone Tower", "Well of Poison Area", "Knuckle Head"}.isdisjoint(
        longevity_names
    )
    assert "Steam & Sauna Spa" in spa_names
    assert {"Milano Nail Spa", "Third Space Counselling", "THIRD SPACE CONTRACTING LTD"}.isdisjoint(
        spa_names
    )
    assert "Iron Lab Strength" in strength_names
    assert "Dragon Temple Martial Arts" not in strength_names
    assert "spa_thermal" not in normalize_categories("Third Space Counselling")


def _bundle_member_names(bundles: list[dict[str, Any]], label: str) -> set[str]:
    bundle = next(item for item in bundles if item["label"] == label)
    return {str(member["operator"]["name"]) for member in bundle["memberships"]}


def _operator(
    operator_id: str,
    name: str,
    municipality: str,
    neighborhood: str,
    *,
    categories: list[str] | None = None,
    raw_payloads: list[dict[str, Any]] | None = None,
    lat: float = 49.28,
    lng: float = -123.12,
    address: str = "123 Example Street, Vancouver, BC",
) -> dict[str, Any]:
    return {
        "id": operator_id,
        "name": name,
        "normalized_name": name.lower(),
        "organization_id": None,
        "organization_name": None,
        "categories": categories or ["recovery_contrast_therapy"],
        "venue_class": "commercial_wellness",
        "address": address,
        "municipality": municipality,
        "neighborhood": neighborhood,
        "lat": lat,
        "lng": lng,
        "first_seen_at": datetime(2026, 5, 1, tzinfo=timezone.utc),
        "is_new_180d": False,
        "source_refs": [{**SOURCE_REF, "source_record_id": operator_id}],
        "confidence_score": 0.9,
        "raw_payloads": raw_payloads or [],
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
