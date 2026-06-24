from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime, timezone

from apps.jobs.adapters.statcan_wds import (
    CATEGORY_BUSINESS_NAICS,
    LIVE_GEOGRAPHIES,
    StatCanWdsAdapter,
)
from apps.jobs.analytics.denominators import (
    InMemoryDenominatorRepository,
    run_statcan_denominators,
)
from apps.jobs.analytics.entity_resolution import EntityMatch, _dedupe_active_duplicates
from apps.jobs.analytics.graph import (
    build_graph_rows,
    connected_component_communities,
    degree_centrality,
)
from apps.jobs.analytics.influence import components_for_person, why_person_appears
from apps.jobs.analytics.opportunity import ScoreComponents
from apps.jobs.analytics.propositions import proposition_from_heatmap_cell
from apps.jobs.analytics.trends import (
    FixturePeerCityTrendProvider,
    InMemoryTrendRepository,
    run_peer_city_trends,
)


def test_statcan_denominator_adapter_uses_fixture_and_bc_gate() -> None:
    repository = InMemoryDenominatorRepository()
    metrics = run_statcan_denominators(StatCanWdsAdapter(mode="fixture"), repository)

    assert metrics.records_fetched >= 6
    assert metrics.records_persisted > metrics.records_fetched
    assert metrics.records_rejected == 0
    assert "933" in repository.geographies
    assert all(denominator.source_refs for denominator in repository.denominators.values())
    assert any(
        denominator.metric == "business_count"
        and denominator.category == "recovery_contrast_therapy"
        for denominator in repository.denominators.values()
    )
    assert all(
        denominator.payload["demand_source"] == "statcan_wds_fixture"
        for denominator in repository.denominators.values()
    )
    assert all(
        denominator.payload["demand_source_status"] == "fixture"
        for denominator in repository.denominators.values()
    )


def test_statcan_denominator_adapter_fetches_live_profile_and_business_counts(
    tmp_path,
) -> None:
    adapter = StatCanWdsAdapter(mode="live", client=FakeStatCanClient(), cache_dir=tmp_path)

    records = adapter.fetch()

    vancouver = next(record for record in records if record["geo_code"] == "5915022")
    assert vancouver["demand_source_status"] == "live"
    assert vancouver["live_attempted"] is True
    population = next(
        denominator
        for denominator in vancouver["denominators"]
        if denominator["metric"] == "population"
    )
    recovery = next(
        denominator
        for denominator in vancouver["denominators"]
        if denominator.get("category") == "recovery_contrast_therapy"
        and denominator.get("source_table") == "33-10-1016-01"
    )
    employment_size = next(
        denominator
        for denominator in vancouver["denominators"]
        if denominator.get("source_table") == "33-10-0766-01"
        and denominator.get("category") == "spa_thermal"
        and denominator.get("employment_size") == "1 to 4 employees"
    )
    assert population["value"] == 662248.0
    assert recovery["value"] == 650.0
    assert recovery["naics_code"] == "8121"
    assert recovery["source_vector"] == "v-5915022-8121"
    assert recovery["source_refs"][0]["source_name"] == "statcan_business_counts"
    assert employment_size["value"] == 341.0
    assert employment_size["source_refs"][0]["source_name"] == "statcan_business_counts_33_10_0766"


def test_proposition_template_exposes_raw_demand_and_sources() -> None:
    source_refs = [
        {
            "source_name": "statcan_wds",
            "url": "https://www.statcan.gc.ca/en/developers/wds",
            "trust_tier": "official",
            "seen_at": "2026-06-18T00:00:00Z",
            "source_record_id": "wds",
            "licence": "Statistics Canada terms",
        }
    ]
    proposition = proposition_from_heatmap_cell(
        {
            "heatmap_cell_id": "heat_recovery_mount_pleasant",
            "category": "recovery_contrast_therapy",
            "geo_code": "nh_5915022_mount_pleasant",
            "geo_name": "Mount Pleasant",
            "geo_level": "neighborhood",
            "supply_count": 2,
            "population": 44149.8667,
            "business_count": 17.3333,
            "opportunity_score": 0.78,
            "confidence_score": 0.63,
            "component_breakdown": {},
            "source_refs": source_refs,
            "parent_geo_name": "Vancouver",
            "trace_payload": {
                "competitor_count_within_radius": 3,
                "competitor_radius_km": 4.0,
                "nearest_competitors": [
                    {
                        "operator_id": "op_aetherhaus",
                        "name": "AetherHaus",
                        "distance_km": 1.2,
                        "municipality": "Vancouver",
                        "neighborhood": "West End",
                        "source_refs": source_refs,
                    }
                ],
                "demand_source": "statcan_wds_fixture",
                "demand_source_status": "fixture_fallback",
                "raw_parent_population": 662248,
                "raw_parent_business_count": 260,
                "population_allocation_share": 0.066667,
            },
        }
    )

    assert proposition["headline"] == (
        "Mount Pleasant: source-backed recovery and contrast therapy whitespace"
    )
    assert proposition["competitor_count_within_radius"] == 3
    assert proposition["nearest_competitors"][0]["name"] == "AetherHaus"
    assert proposition["population"] == 44149.8667
    assert proposition["market_sizing_line"].startswith("Catchment spend context:")
    assert "context for demand, not capturable revenue" in proposition["market_sizing_line"]
    assert "AetherHaus" in proposition["thesis"]
    assert "fixture-backed" in proposition["confidence_narrative"]
    assert proposition["confidence_score"] < 0.63
    assert any(
        ref["source_name"] == "statcan_survey_household_spending"
        for ref in proposition["source_refs"]
    )


def test_peer_city_trends_fixture_is_stub_backed_and_deterministic() -> None:
    repository = InMemoryTrendRepository()
    metrics = run_peer_city_trends(FixturePeerCityTrendProvider(), repository)

    assert metrics.records_fetched == 30
    assert metrics.records_persisted == 30
    vancouver_cold_plunge = repository.trends[("cold plunge", "Vancouver")]
    assert vancouver_cold_plunge.is_stub is True
    assert vancouver_cold_plunge.growth_class == "breakout"
    assert vancouver_cold_plunge.series[-1]["value"] == 80


def test_opportunity_score_requires_full_component_breakdown() -> None:
    components = ScoreComponents(
        demand_proxy=0.8,
        low_supply_density=0.6,
        category_growth=0.4,
        target_demo_fit=0.7,
        transit_access=0.5,
        event_community_activity=0.3,
        source_confidence=0.9,
    )

    assert set(components.as_dict()) == {
        "demand_proxy",
        "low_supply_density",
        "category_growth",
        "target_demo_fit",
        "transit_access",
        "event_community_activity",
        "source_confidence",
    }
    assert components.score() == 0.635


def test_entity_resolution_keeps_highest_confidence_active_duplicate() -> None:
    low = EntityMatch(
        entity_type="operator",
        survivor_id="op_a",
        duplicate_id="op_dup",
        status="candidate",
        confidence_score=0.84,
        deterministic_rule="review",
        provenance={},
        source_refs=[],
    )
    high = EntityMatch(
        entity_type="operator",
        survivor_id="op_b",
        duplicate_id="op_dup",
        status="merged",
        confidence_score=0.97,
        deterministic_rule="exact",
        provenance={},
        source_refs=[],
    )

    matches = _dedupe_active_duplicates([low, high])

    assert matches == [high]


def test_graph_builds_public_affiliation_edges_and_centrality() -> None:
    source_refs = [
        {
            "source_name": "manual_people_csv",
            "url": "https://example.com",
            "trust_tier": "informal",
            "seen_at": "2026-06-18T00:00:00Z",
            "source_record_id": "fixture",
            "licence": "fixture",
        }
    ]
    people = [
        {
            "id": "person_a",
            "name": "A Public Operator",
            "roles": ["Operator"],
            "affiliations": [{"organization_name": "AetherHaus", "role": "Public operator team"}],
            "source_refs": source_refs,
            "confidence_score": 0.8,
        }
    ]
    operators = [
        {
            "id": "op_aetherhaus",
            "name": "AetherHaus",
            "normalized_name": "aetherhaus",
            "organization_id": None,
            "categories": ["recovery_contrast_therapy"],
            "source_refs": source_refs,
            "confidence_score": 0.85,
        }
    ]

    nodes, edges = build_graph_rows(people, [], operators, [])
    centrality = degree_centrality(nodes, edges)
    communities = connected_component_communities(nodes, edges)

    assert len(nodes) == 2
    assert len(edges) == 1
    assert edges[0].edge_type == "employee"
    assert centrality["node_person_person_a"] == 1
    assert communities["node_person_person_a"] == communities["node_operator_op_aetherhaus"]


def test_influence_components_use_public_professional_fields_only() -> None:
    person = {
        "id": "person_bonnie_henry",
        "name": "Dr. Bonnie Henry",
        "roles": ["Provincial Health Officer"],
        "affiliations": [
            {
                "organization_name": "Government of British Columbia",
                "role": "Provincial Health Officer",
            }
        ],
        "public_profiles": {"primary": "https://www2.gov.bc.ca/"},
        "confidence_score": 0.95,
        "last_seen_at": datetime.now(timezone.utc),
        "network_centrality": 0.7,
    }

    components = components_for_person(
        person=person,
        media_count=2,
        media_confidence=0.8,
        event_count=1,
    )
    explanation = why_person_appears(person, components, media_count=2, event_count=1)

    assert components.institutional_authority == 0.95
    assert components.research_or_clinical_leadership == 0.85
    assert components.locality_multiplier > 1
    assert components.final_score() > 0
    assert "Public professional role" in explanation


class FakeStatCanClient:
    def get_bytes(self, url: str, *, accept: str) -> bytes:
        if "profile/sdmx/rest/data" in url:
            return _profile_csv(url).encode("utf-8")
        if "getFullTableDownloadCSV/33100766/en" in url:
            return b'{"status":"SUCCESS","object":"https://www150.statcan.gc.ca/n1/tbl/csv/33100766-eng.zip"}'
        if "33101016-eng.zip" in url:
            return _business_counts_zip()
        if "33100766-eng.zip" in url:
            return _business_counts_employment_size_zip()
        raise AssertionError(f"unexpected StatCan URL {url} with {accept}")


def _profile_csv(url: str) -> str:
    rows = []
    for geography in LIVE_GEOGRAPHIES:
        if geography.census_profile_flow not in url:
            continue
        value = 662248 if geography.geo_code == "5915022" else 100000
        rows.append(
            {
                "DATAFLOW": f"STC_CP:{geography.census_profile_flow}(1.3)",
                "FREQ": "A5",
                "TIME_PERIOD": "2021",
                "REF_AREA": geography.dguid,
                "GENDER": "1",
                "CHARACTERISTIC": "1",
                "STATISTIC": "1",
                "OBS_VALUE": str(value),
                "DECIMALS": "0",
                "ALT_GEO_CODE": geography.geo_code,
            }
        )
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _business_counts_zip() -> bytes:
    unique_codes = {
        str(config["code"]): str(config["label"])
        for config in CATEGORY_BUSINESS_NAICS.values()
    }
    output = io.StringIO()
    fieldnames = [
        "REF_DATE",
        "GEO",
        "DGUID",
        "Employment size",
        "North American Industry Classification System (NAICS)",
        "UOM",
        "UOM_ID",
        "SCALAR_FACTOR",
        "SCALAR_ID",
        "VECTOR",
        "COORDINATE",
        "VALUE",
        "STATUS",
        "SYMBOL",
        "TERMINATED",
        "DECIMALS",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for geo_index, geography in enumerate(LIVE_GEOGRAPHIES, start=1):
        for code_index, (code, label) in enumerate(unique_codes.items(), start=1):
            value = 650 if geography.geo_code == "5915022" and code == "8121" else 25
            writer.writerow(
                {
                    "REF_DATE": "2025-01",
                    "GEO": geography.geo_name,
                    "DGUID": geography.dguid,
                    "Employment size": "Total, with employees",
                    "North American Industry Classification System (NAICS)": f"{label} [{code}]",
                    "UOM": "Number",
                    "UOM_ID": "223",
                    "SCALAR_FACTOR": "units",
                    "SCALAR_ID": "0",
                    "VECTOR": f"v-{geography.geo_code}-{code}",
                    "COORDINATE": f"{geo_index}.1.{code_index}",
                    "VALUE": str(value),
                    "STATUS": "",
                    "SYMBOL": "",
                    "TERMINATED": "",
                    "DECIMALS": "0",
                }
            )
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("33101016.csv", output.getvalue())
    return zip_buffer.getvalue()


def _business_counts_employment_size_zip() -> bytes:
    rows = [
        ("Total, with employees", "Personal care services", "8121", 648),
        ("1 to 4 employees", "Personal care services", "8121", 341),
        ("Total, with employees", "Other amusement and recreation industries", "7139", 201),
        ("1 to 4 employees", "Other amusement and recreation industries", "7139", 68),
        ("Total, with employees", "Offices of other health practitioners", "6213", 753),
        ("1 to 4 employees", "Offices of other health practitioners", "6213", 531),
        ("Total, with employees", "Health care and social assistance", "62", 4474),
        ("1 to 4 employees", "Health care and social assistance", "62", 3027),
    ]
    output = io.StringIO()
    fieldnames = [
        "REF_DATE",
        "GEO",
        "DGUID",
        "Employment size",
        "North American Industry Classification System (NAICS)",
        "UOM",
        "UOM_ID",
        "SCALAR_FACTOR",
        "SCALAR_ID",
        "VECTOR",
        "COORDINATE",
        "VALUE",
        "STATUS",
        "SYMBOL",
        "TERMINATED",
        "DECIMALS",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for geography in LIVE_GEOGRAPHIES:
        for employment_size, label, code, value in rows:
            writer.writerow(
                {
                    "REF_DATE": "2024-07",
                    "GEO": geography.geo_name,
                    "DGUID": geography.dguid,
                    "Employment size": employment_size,
                    "North American Industry Classification System (NAICS)": f"{label} [{code}]",
                    "UOM": "Number",
                    "UOM_ID": "223",
                    "SCALAR_FACTOR": "units",
                    "SCALAR_ID": "0",
                    "VECTOR": f"v-0766-{geography.geo_code}-{code}-{employment_size}",
                    "COORDINATE": f"{geography.geo_code}.{code}.{employment_size}",
                    "VALUE": str(value if geography.geo_code == "5915022" else 5),
                    "STATUS": "",
                    "SYMBOL": "",
                    "TERMINATED": "",
                    "DECIMALS": "0",
                }
            )
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("33100766.csv", output.getvalue())
    return zip_buffer.getvalue()
