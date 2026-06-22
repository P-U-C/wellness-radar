from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apps.jobs.adapters.manual_seed import ManualRecoverySeedAdapter
from apps.jobs.adapters.municipal_facilities import (
    MUNICIPAL_SOURCES,
    MunicipalFacilitiesAdapter,
)
from apps.jobs.adapters.orgbook_bc import OrgBookBCEnrichmentAdapter
from apps.jobs.adapters.osm_overpass import OsmOverpassAdapter
from apps.jobs.adapters.rss import (
    BCGovHealthNewsAdapter,
    HealthCanadaRecallsAdapter,
    RssFeedAdapter,
)
from apps.jobs.enrichment.ai_signals import DeterministicSignalEnricher, SignalEnrichmentService
from apps.jobs.importers.people_csv import import_people_csv
from apps.jobs.runner import (
    InMemoryRepository,
    run_adapter,
    run_event_adapter,
    run_orgbook_enrichment,
)

FIXTURES = Path(__file__).parent / "fixtures"


class FakeResponse:
    def __init__(self, payload: Any, *, text: str | None = None) -> None:
        self.payload = payload
        self.text = text if text is not None else json.dumps(payload)

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self.payload


class FakeHttpClient:
    def __init__(self, payload: Any = None, text: str | None = None) -> None:
        self.payload = payload
        self.text = text
        self.requests: list[dict[str, Any]] = []

    def get(self, url: str, params: dict[str, Any] | None = None) -> FakeResponse:
        self.requests.append({"method": "GET", "url": url, "params": params})
        return FakeResponse(self.payload, text=self.text)

    def post(self, url: str, data: dict[str, Any] | None = None) -> FakeResponse:
        self.requests.append({"method": "POST", "url": url, "data": data})
        return FakeResponse(self.payload, text=self.text)


class FailingHttpClient:
    def get(self, url: str, params: dict[str, Any] | None = None) -> FakeResponse:
        raise RuntimeError(f"portal unavailable: {url}")


def load_json(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


def test_osm_overpass_adapter_normalizes_fixture_and_rejects_wa() -> None:
    client = FakeHttpClient(load_json("osm_overpass.json"))
    adapter = OsmOverpassAdapter(limit=10, client=client)  # type: ignore[arg-type]
    repository = InMemoryRepository()

    metrics = run_adapter(adapter, repository)

    assert client.requests[0]["method"] == "POST"
    assert metrics.records_fetched == 3
    assert metrics.records_persisted == 2
    assert metrics.records_rejected == 1
    assert len(repository.operators) == 2
    assert all(operator.source_refs for operator in repository.operators.values())
    art = next(
        operator for operator in repository.operators.values() if operator.name == "Art of Sauna"
    )
    assert art.phone == "+1 604 555 0100"
    assert art.website == "https://artofsauna.ca/"
    assert art.social_links["instagram"] == "https://www.instagram.com/artofsauna"
    assert {contact["type"] for contact in art.contacts} == {
        "email",
        "phone",
        "social",
        "website",
    }
    assert all(contact["source_ref"]["source_name"] == adapter.name for contact in art.contacts)


def test_osm_overpass_query_uses_wide_tag_batches() -> None:
    client = FakeHttpClient({"elements": []})
    adapter = OsmOverpassAdapter(client=client)  # type: ignore[arg-type]

    records = adapter.fetch()

    assert records == []
    posted_queries = [str(request["data"]["data"]) for request in client.requests]
    assert any('nwr["sport"]' in query for query in posted_queries)
    assert any("fitness_station" in query and "ice_rink" in query for query in posted_queries)
    assert any('nwr["sauna"]' in query for query in posted_queries)
    assert all("[timeout:90]" in query for query in posted_queries)
    assert all("out center 2000" in query for query in posted_queries)


def test_osm_overpass_new_sport_tags_classify_to_specific_categories() -> None:
    adapter = OsmOverpassAdapter()
    raw = {
        "type": "node",
        "id": 4242,
        "lat": 49.25,
        "lon": -123.1,
        "tags": {
            "addr:city": "Vancouver",
            "addr:province": "BC",
            "name": "Creekside Pickleball Courts",
            "sport": "pickleball",
        },
    }

    operator = adapter.normalize(raw, "raw_osm_pickleball")[0]

    assert "racquet_court_sports" in operator.categories
    assert operator.source_refs[0]["url"] == "https://www.openstreetmap.org/node/4242"
    assert operator.payload["tags"]["sport"] == "pickleball"


def test_municipal_facilities_falls_back_to_recorded_source_fixture() -> None:
    adapter = MunicipalFacilitiesAdapter(
        limit=5,
        client=FailingHttpClient(),  # type: ignore[arg-type]
        sources=(MUNICIPAL_SOURCES[0],),
        fixture_dir=FIXTURES,
    )
    repository = InMemoryRepository()

    metrics = run_adapter(adapter, repository)

    assert metrics.records_fetched == 1
    assert metrics.records_persisted == 1
    operator = next(iter(repository.operators.values()))
    assert operator.name == "Tantalus Park"
    assert operator.municipality == "West Vancouver"
    assert "public_recreation" in operator.categories
    assert operator.source_refs
    assert {ref["source_name"] for ref in operator.source_refs} == {
        "municipal_facilities",
        "municipal_facilities_west_vancouver",
    }
    assert operator.payload["source_status"] == "fixture_fallback"
    raw_payload = next(iter(repository.raw_payloads.values()))
    assert raw_payload["_source_error"].startswith("portal unavailable")
    assert raw_payload["_source"]["registry_name"] == "municipal_facilities_west_vancouver"


def test_manual_recovery_seed_contains_required_private_alpha_records() -> None:
    adapter = ManualRecoverySeedAdapter(limit=100)
    repository = InMemoryRepository()

    metrics = run_adapter(adapter, repository)

    assert metrics.records_persisted >= 10
    assert "AetherHaus" in {operator.name for operator in repository.operators.values()}
    assert all(
        operator.source_refs[0]["source_name"] == "manual_seed"
        for operator in repository.operators.values()
    )
    assert all(operator.website for operator in repository.operators.values())
    assert all(operator.contacts for operator in repository.operators.values())


def test_orgbook_enrichment_matches_exact_legal_name_and_records_unmatched() -> None:
    repository = InMemoryRepository()
    seed = ManualRecoverySeedAdapter(limit=1)
    run_adapter(seed, repository)
    tality_raw = {
        "name": "Tality Wellness",
        "address": "107 East 3rd Avenue, Vancouver, BC",
        "municipality": "Vancouver",
        "province": "BC",
        "country": "CA",
        "lat": "49.2676",
        "lng": "-123.1018",
        "categories": "recovery_contrast_therapy",
        "status": "open",
        "source_url": "https://www.talitywellness.ca/",
        "source_record_id": "tality_test",
        "confidence_score": "0.9",
    }
    raw_payload_id = repository.upsert_raw_payload("manual_seed", "tality_test", tality_raw)
    operator = seed.normalize(tality_raw, raw_payload_id)[0]
    repository.upsert_operator(operator)

    adapter = OrgBookBCEnrichmentAdapter(
        client=FakeHttpClient(load_json("orgbook_tality.json"))  # type: ignore[arg-type]
    )
    metrics = run_orgbook_enrichment(adapter, repository, limit=10)

    assert metrics.records_persisted >= 2
    matched = [org for org in repository.organizations.values() if org.orgbook_id]
    unmatched = [org for org in repository.organizations.values() if not org.orgbook_id]
    assert matched[0].orgbook_id == "2381381"
    assert unmatched


def test_local_rss_adapter_creates_bc_gated_wellness_signal() -> None:
    xml = (FIXTURES / "local_rss.xml").read_text()
    adapter = RssFeedAdapter(limit=10, client=FakeHttpClient(text=xml))  # type: ignore[arg-type]
    adapter.feeds = adapter.feeds[:1]
    repository = InMemoryRepository()

    metrics = run_event_adapter(adapter, repository)

    assert metrics.records_fetched == 2
    assert metrics.records_persisted == 1
    signal = next(iter(repository.signals.values()))
    assert signal.source_name == "local_rss"
    assert signal.source_refs


def test_official_rss_adapters_create_signals_without_network() -> None:
    bc_xml = (FIXTURES / "bc_gov_health.xml").read_text()
    recall_xml = (FIXTURES / "health_canada_recalls.xml").read_text()
    repository = InMemoryRepository()

    bc_metrics = run_event_adapter(
        BCGovHealthNewsAdapter(client=FakeHttpClient(text=bc_xml)),  # type: ignore[arg-type]
        repository,
    )
    recall_metrics = run_event_adapter(
        HealthCanadaRecallsAdapter(client=FakeHttpClient(text=recall_xml)),  # type: ignore[arg-type]
        repository,
    )

    assert bc_metrics.records_persisted == 1
    assert recall_metrics.records_persisted == 1
    assert {signal.trust_tier for signal in repository.signals.values()} == {"official"}


def test_manual_people_import_and_deterministic_ai_enrichment() -> None:
    repository = InMemoryRepository()
    bc_gov_xml = (FIXTURES / "bc_gov_health.xml").read_text()
    run_event_adapter(
        BCGovHealthNewsAdapter(client=FakeHttpClient(text=bc_gov_xml)),  # type: ignore[arg-type]
        repository,
    )

    people_metrics = import_people_csv(repository)
    enriched = SignalEnrichmentService(
        repository,
        enricher=DeterministicSignalEnricher(),
    ).enrich_pending()

    assert people_metrics.records_persisted >= 4
    assert repository.people
    assert enriched == 1
    signal = next(iter(repository.signals.values()))
    assert signal.why_it_matters
    assert signal.ai_model == "deterministic-local-v1"
    assert "why_it_matters" in signal.ai_generated_fields
