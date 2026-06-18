from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from packages.schemas.canonical import SourceRef
from packages.shared.ids import stable_id

DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "statcan_m3_denominators.json"
)


@dataclass(frozen=True)
class StatCanGeography:
    geo_code: str
    geo_level: str
    geo_name: str
    parent_geo_code: str | None
    lat: float | None
    lng: float | None
    bc_gate_text: str
    source_name: str
    source_refs: list[dict[str, Any]]
    confidence_score: float
    payload: dict[str, Any]


@dataclass(frozen=True)
class StatCanDenominator:
    id: str
    geo_code: str
    geo_level: str
    geo_name: str
    metric: str
    category: str | None
    naics_code: str | None
    value: float
    unit: str
    reference_period: str
    source_name: str
    source_refs: list[dict[str, Any]]
    confidence_score: float
    payload: dict[str, Any]


class StatCanWdsAdapter:
    name = "statcan_wds"
    family = "denominator/statistics"
    cadence = "annual/as_released"
    trust_tier = "official"
    geo_aware = True
    wds_base_url = "https://www150.statcan.gc.ca/t1/wds/rest"

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        fixture_path: Path | None = DEFAULT_FIXTURE_PATH,
    ) -> None:
        self.client = client or httpx.Client(timeout=30.0)
        self.fixture_path = fixture_path

    def fetch(self) -> list[dict[str, Any]]:
        if self.fixture_path is not None:
            payload = json.loads(self.fixture_path.read_text())
            shared_refs = payload.get("source_refs", [])
            records = payload.get("records", [])
            return [
                {
                    **record,
                    "fixture_recorded_at": payload.get("fixture_recorded_at"),
                    "fixture_note": payload.get("fixture_note"),
                    "source_refs": [*shared_refs, *record.get("source_refs", [])],
                }
                for record in records
            ]

        response = self.client.get(f"{self.wds_base_url}/getAllCubesListLite")
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and "records" in payload:
            return list(payload["records"])
        raise RuntimeError("StatCan live WDS fetch must return normalized denominator records")

    def source_record_id(self, raw: dict[str, Any]) -> str:
        return str(raw["geo_code"])

    def normalize(
        self, raw: dict[str, Any], raw_payload_id: str
    ) -> tuple[StatCanGeography, list[StatCanDenominator]]:
        source_refs = raw.get("source_refs") or [
            SourceRef(
                source_name=self.name,
                url="https://www.statcan.gc.ca/en/developers/wds",
                trust_tier=self.trust_tier,
                seen_at=str(raw.get("fixture_recorded_at") or "2026-06-18T00:00:00Z"),
                source_record_id=self.source_record_id(raw),
                licence="Statistics Canada terms",
            ).as_dict()
        ]
        geography = StatCanGeography(
            geo_code=str(raw["geo_code"]),
            geo_level=str(raw["geo_level"]),
            geo_name=str(raw["geo_name"]),
            parent_geo_code=raw.get("parent_geo_code"),
            lat=_optional_float(raw.get("lat")),
            lng=_optional_float(raw.get("lng")),
            bc_gate_text=str(raw.get("bc_gate_text") or raw.get("geo_name") or ""),
            source_name=self.name,
            source_refs=source_refs,
            confidence_score=_optional_float(raw.get("confidence_score")) or 0.9,
            payload={
                "raw_payload_id": raw_payload_id,
                "fixture_note": raw.get("fixture_note"),
                "geo_code": raw.get("geo_code"),
            },
        )
        denominators = [
            self._denominator_from_raw(raw, denominator, raw_payload_id, source_refs)
            for denominator in raw.get("denominators", [])
        ]
        return geography, denominators

    def _denominator_from_raw(
        self,
        raw: dict[str, Any],
        denominator: dict[str, Any],
        raw_payload_id: str,
        source_refs: list[dict[str, Any]],
    ) -> StatCanDenominator:
        metric = str(denominator["metric"])
        category = denominator.get("category")
        naics_code = denominator.get("naics_code")
        reference_period = str(denominator["reference_period"])
        denominator_id = stable_id(
            "den",
            raw["geo_code"],
            metric,
            category,
            naics_code,
            reference_period,
        )
        return StatCanDenominator(
            id=denominator_id,
            geo_code=str(raw["geo_code"]),
            geo_level=str(raw["geo_level"]),
            geo_name=str(raw["geo_name"]),
            metric=metric,
            category=str(category) if category else None,
            naics_code=str(naics_code) if naics_code else None,
            value=float(denominator["value"]),
            unit=str(denominator["unit"]),
            reference_period=reference_period,
            source_name=self.name,
            source_refs=source_refs,
            confidence_score=float(denominator.get("confidence_score", 0.8)),
            payload={
                "raw_payload_id": raw_payload_id,
                "fixture_note": raw.get("fixture_note"),
                "source_metric": metric,
            },
        )


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str | int | float):
        raise TypeError(f"cannot convert {type(value).__name__} to float")
    return float(value)
