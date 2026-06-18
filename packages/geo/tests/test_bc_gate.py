from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from packages.geo.bc_gate import CanonicalGeoRecord, GeoGateResult, bc_gate, log_rejected_record

FIXTURE = Path(__file__).parents[1] / "fixtures" / "bc_gate_cases.json"


def _record(case: dict[str, Any]) -> CanonicalGeoRecord:
    return CanonicalGeoRecord(
        source_name="fixture",
        title=case.get("title"),
        address=case.get("address"),
        municipality=case.get("municipality"),
        province=case.get("province"),
        country=case.get("country", "CA"),
        lat=case.get("lat"),
        lng=case.get("lng"),
        text=case.get("text"),
        statcan_geo_code=case.get("statcan_geo_code"),
        raw=case,
    )


CASES = json.loads(FIXTURE.read_text())


@pytest.mark.parametrize(
    "case", CASES["accepted"], ids=[case["title"] for case in CASES["accepted"]]
)
def test_bc_gate_accepts_bc_cases(case: dict[str, Any]) -> None:
    result = bc_gate(_record(case))
    assert result.passes, result.reason
    assert result.confidence >= 0.6


@pytest.mark.parametrize(
    "case", CASES["rejected"], ids=[case["title"] for case in CASES["rejected"]]
)
def test_bc_gate_rejects_wa_contamination(case: dict[str, Any]) -> None:
    result = bc_gate(_record(case))
    assert not result.passes
    assert result.reason


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...] | None]] = []

    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> None:
        self.calls.append((query, params))


def test_log_rejected_record_writes_rejection() -> None:
    session = FakeSession()
    record = _record(CASES["rejected"][0])
    log_rejected_record(
        session,
        record,
        GeoGateResult(False, "structured province is Washington", 0.01),
        "raw_fixture_1",
    )

    assert len(session.calls) == 1
    query, params = session.calls[0]
    assert "INSERT INTO rejected_record" in query
    assert params is not None
    assert params[0] == "fixture"
    assert params[1] == "structured province is Washington"
    assert params[2] == "raw_fixture_1"
