from __future__ import annotations

from typing import Any

from apps.jobs.adapters.city_vancouver_building_permits import (
    CityVancouverBuildingPermitsAdapter,
)
from apps.jobs.runner import InMemoryRepository, run_event_adapter


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


def test_city_building_permits_emit_bc_gated_supply_pipeline_signal() -> None:
    bc_record = {
        "permitnumber": "BP-2022-00005",
        "issuedate": "2022-03-08",
        "projectvalue": 150000,
        "typeofwork": "Addition / Alteration",
        "address": "1287 HAMILTON STREET, Vancouver, BC V1V 1V1",
        "projectdescription": "Interior alterations to change Restaurant Shell to Fitness Studio.",
        "propertyuse": ["Cultural/Recreational Uses"],
        "specificusecategory": ["Fitness Centre"],
        "applicant": "Barbara Bent DBA: Lagree West Fitness Ltd",
        "buildingcontractor": None,
        "geolocalarea": "Downtown",
        "geo_point_2d": {"lon": -123.1240518, "lat": 49.273996},
    }
    wa_record = {
        **bc_record,
        "permitnumber": "BP-WA-98660",
        "address": "100 Main Street, Vancouver, WA 98660",
        "geo_point_2d": {"lon": -122.6716, "lat": 45.6387},
    }
    fake_client = FakeClient({"results": [bc_record, wa_record]})
    adapter = CityVancouverBuildingPermitsAdapter(
        limit=2,
        client=fake_client,  # type: ignore[arg-type]
    )
    repository = InMemoryRepository()

    metrics = run_event_adapter(adapter, repository)

    assert metrics.records_fetched == 2
    assert metrics.records_persisted == 1
    assert metrics.records_rejected == 1
    signal = next(iter(repository.signals.values()))
    assert signal.type == "supply_pipeline_permit"
    assert signal.related_operator_id is None
    assert signal.source_refs[0]["source_name"] == adapter.name
    assert "Fitness Centre" in next(iter(repository.source_events.values())).payload[
        "specific_use_category"
    ]
    assert "search(specificusecategory, 'Fitness')" in fake_client.requests[0]["params"]["where"]
