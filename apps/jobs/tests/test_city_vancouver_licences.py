from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apps.jobs.adapters.city_vancouver_licences import CityVancouverBusinessLicencesAdapter
from apps.jobs.runner import InMemoryRepository, run_adapter
from packages.geo.bc_gate import CanonicalGeoRecord, bc_gate

FIXTURE = Path(__file__).parent / "fixtures" / "city_vancouver_business_licences.json"


def fixture_payload() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text())


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.requests: list[dict[str, Any]] = []

    def get(self, url: str, params: dict[str, Any]) -> FakeResponse:
        self.requests.append({"url": url, "params": params})
        return FakeResponse(self.payload)


def test_city_adapter_fetch_uses_recorded_fixture_without_live_network() -> None:
    client = FakeClient(fixture_payload())
    adapter = CityVancouverBusinessLicencesAdapter(limit=3, client=client)  # type: ignore[arg-type]

    records = adapter.fetch()

    assert len(records) == 3
    assert client.requests[0]["url"].endswith("/business-licences/records")
    assert "province = 'BC'" in client.requests[0]["params"]["where"]


def test_city_adapter_normalizes_with_provenance_and_bc_gate() -> None:
    adapter = CityVancouverBusinessLicencesAdapter(limit=3)
    raw = fixture_payload()["results"][0]
    raw_payload_id = "raw_fixture"

    operators = adapter.normalize(raw, raw_payload_id)

    assert len(operators) == 1
    operator = operators[0]
    assert operator.name == "Tommy Lu RMT"
    assert operator.categories == ["allied_health"]
    assert operator.status == "open"
    assert operator.source_refs[0]["source_name"] == adapter.name
    assert operator.source_refs[0]["url"]
    assert operator.lat == 49.2688414991874
    assert operator.lng == -123.101196475776

    gate = bc_gate(
        CanonicalGeoRecord(
            source_name=operator.source_name,
            title=operator.name,
            address=operator.address,
            municipality=operator.municipality,
            province=operator.province,
            country=operator.country,
            lat=operator.lat,
            lng=operator.lng,
            text=str(operator.payload),
            statcan_geo_code=None,
            raw=raw,
        )
    )
    assert gate.passes


class FixtureAdapter(CityVancouverBusinessLicencesAdapter):
    def __init__(self, records: list[dict[str, Any]]) -> None:
        super().__init__(limit=len(records))
        self.records = records

    def fetch(self) -> list[dict[str, Any]]:
        return self.records


def test_runner_upserts_idempotently_and_logs_wa_rejection() -> None:
    records = fixture_payload()["results"]
    wa_record = {
        **records[0],
        "licencersn": "wa-98660",
        "licencenumber": "WA-98660",
        "businessname": "Vancouver WA Wellness",
        "businesstradename": "Clark County Wellness",
        "city": "Vancouver",
        "province": "WA",
        "country": "US",
        "postalcode": "98660",
        "geo_point_2d": None,
        "geom": None,
    }
    adapter = FixtureAdapter([*records, wa_record])
    repository = InMemoryRepository()

    first = run_adapter(adapter, repository)
    second = run_adapter(adapter, repository)

    assert first.records_fetched == 4
    assert first.records_persisted == 3
    assert first.records_rejected == 1
    assert second.records_persisted == 3
    assert len(repository.operators) == 3
    assert len(repository.source_events) == 3
    assert len(repository.signals) == 3
    assert len(repository.rejected) == 2
    assert repository.source_runs[1]["status"] == "success"
    assert repository.source_runs[2]["status"] == "success"
    audit_actions = {entry["action"] for entry in repository.audit_logs}
    assert {
        "adapter_run_started",
        "adapter_run_completed",
        "record_rejected",
        "source_event_upserted",
        "signal_upserted",
    } <= audit_actions
