from __future__ import annotations

from datetime import datetime, timezone

from apps.jobs.analytics.bundles import synthesize_bundles

SOURCE_REF = {
    "source_name": "manual_seed",
    "url": "https://example.test/operator",
    "trust_tier": "informal",
    "seen_at": "2026-06-22T00:00:00Z",
    "source_record_id": "operator",
    "licence": "fixture",
}


def test_bundle_synthesis_is_data_driven_and_links_people() -> None:
    now = datetime(2026, 6, 22, 12, 0, tzinfo=timezone.utc)
    operators = [
        _operator(
            "op_aetherhaus",
            "AetherHaus",
            ["recovery_contrast_therapy", "spa_thermal"],
            raw_payloads=[{"tags": {"leisure": "sauna", "amenity": "spa"}}],
        ),
        _operator("op_tality", "Tality Wellness", ["community_social_wellness"]),
        _operator("op_strength", "Iron Lab Strength", ["fitness_movement"]),
        _operator("op_pilates", "Eastside Reformer Pilates", ["fitness_movement"]),
        _operator("op_longevity", "Longevity IV Lounge", ["nutrition_longevity"]),
        _operator(
            "op_physio",
            "Bodywork Physio",
            ["allied_health"],
            raw_payloads=[{"tags": {"healthcare": "physiotherapist"}}],
        ),
    ]
    people = [
        {
            "id": "person_a",
            "name": "A Public Founder",
            "roles": ["Founder"],
            "affiliations": [{"organization_name": "AetherHaus", "role": "Founder"}],
            "public_profiles": {"primary": "https://example.test/person"},
            "influence_score": 0.82,
            "confidence_score": 0.9,
            "source_refs": [SOURCE_REF],
            "influence_source_refs": [SOURCE_REF],
        }
    ]
    signals = [
        {
            "id": "sig_a",
            "type": "operator_observed",
            "severity": "info",
            "title": "AetherHaus observed",
            "occurred_at": now,
            "related_operator_id": "op_aetherhaus",
            "source_refs": [SOURCE_REF],
            "confidence_score": 0.8,
        }
    ]

    bundles = synthesize_bundles(
        operators=operators,
        geographies=_geographies(),
        signals=signals,
        people=people,
        now=now,
    )

    labels = {bundle["label"] for bundle in bundles}
    assert len(bundles) >= 4
    assert "Cold plunge & contrast therapy" in labels
    assert "Boutique strength" in labels
    assert "Yoga & pilates" in labels
    assert "Longevity / IV" in labels

    cold = next(bundle for bundle in bundles if bundle["label"] == "Cold plunge & contrast therapy")
    assert cold["member_count"] >= 1
    assert cold["components"]["formula"]
    assert 0 <= cold["bundle_score"] <= 1
    assert cold["source_refs"]
    assert cold["confidence_score"] < 0.95
    assert cold["memberships"][0]["match_reasons"]["category_matches"]
    assert cold["top_people"][0]["id"] == "person_a"
    assert "AetherHaus" in cold["top_people"][0]["why_appears"]


def _operator(
    operator_id: str,
    name: str,
    categories: list[str],
    raw_payloads: list[dict] | None = None,
) -> dict:
    return {
        "id": operator_id,
        "name": name,
        "normalized_name": name.lower(),
        "organization_id": None,
        "organization_name": None,
        "categories": categories,
        "municipality": "Vancouver",
        "neighborhood": "Mount Pleasant",
        "lat": 49.26,
        "lng": -123.1,
        "first_seen_at": datetime(2026, 5, 1, tzinfo=timezone.utc),
        "source_refs": [SOURCE_REF],
        "confidence_score": 0.9,
        "raw_payloads": raw_payloads or [],
    }


def _geographies() -> list[dict]:
    return [
        {
            "geo_code": "5915022",
            "geo_level": "CSD",
            "geo_name": "Vancouver",
            "parent_geo_code": None,
            "municipality": "Vancouver",
            "geography_source_refs": [SOURCE_REF],
            "geography_confidence": 0.95,
            "geography_payload": {},
            "population_denominator_id": "den_vancouver_population",
            "population": 662248,
            "population_source_refs": [SOURCE_REF],
            "population_confidence": 0.9,
            "population_payload": {"demand_source_status": "fixture"},
        },
        {
            "geo_code": "nh_mount_pleasant",
            "geo_level": "neighborhood",
            "geo_name": "Mount Pleasant",
            "parent_geo_code": "5915022",
            "municipality": "Vancouver",
            "geography_source_refs": [SOURCE_REF],
            "geography_confidence": 0.8,
            "geography_payload": {},
            "population_denominator_id": "den_mount_pleasant_population",
            "population": 44149,
            "population_source_refs": [SOURCE_REF],
            "population_confidence": 0.75,
            "population_payload": {"demand_source_status": "fixture"},
        },
    ]
