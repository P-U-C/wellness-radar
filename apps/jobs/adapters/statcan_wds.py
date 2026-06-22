from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from packages.schemas.canonical import SourceRef
from packages.shared.ids import stable_id

DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "statcan_m3_denominators.json"
)

FetchMode = Literal["auto", "fixture", "live"]

STATCAN_WDS_BASE_URL = "https://www150.statcan.gc.ca/t1/wds/rest"
STATCAN_BUSINESS_COUNTS_PRODUCT_ID = "33101016"
STATCAN_BUSINESS_COUNTS_TABLE_ID = "33-10-1016-01"
STATCAN_BUSINESS_COUNTS_CSV_URL = (
    "https://www150.statcan.gc.ca/n1/tbl/csv/33101016-eng.zip"
)
STATCAN_BUSINESS_COUNTS_TABLE_URL = (
    "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3310101601"
)
STATCAN_CENSUS_PROFILE_BASE_URL = (
    "https://api.statcan.gc.ca/census-recensement/profile/sdmx/rest/data"
)


@dataclass(frozen=True)
class StatCanGeoConfig:
    geo_code: str
    geo_level: str
    geo_name: str
    parent_geo_code: str | None
    dguid: str
    census_profile_flow: str
    lat: float
    lng: float
    bc_gate_text: str


LIVE_GEOGRAPHIES = [
    StatCanGeoConfig(
        geo_code="933",
        geo_level="CMA",
        geo_name="Vancouver CMA",
        parent_geo_code="59",
        dguid="2021S0503933",
        census_profile_flow="DF_CMACA",
        lat=49.255,
        lng=-123.02,
        bc_gate_text="Vancouver CMA 933, British Columbia",
    ),
    StatCanGeoConfig(
        geo_code="5915022",
        geo_level="CSD",
        geo_name="Vancouver",
        parent_geo_code="933",
        dguid="2021A00055915022",
        census_profile_flow="DF_CSD",
        lat=49.2827,
        lng=-123.1207,
        bc_gate_text="Vancouver, BC",
    ),
    StatCanGeoConfig(
        geo_code="5915025",
        geo_level="CSD",
        geo_name="Burnaby",
        parent_geo_code="933",
        dguid="2021A00055915025",
        census_profile_flow="DF_CSD",
        lat=49.2488,
        lng=-122.9805,
        bc_gate_text="Burnaby, BC",
    ),
    StatCanGeoConfig(
        geo_code="5915015",
        geo_level="CSD",
        geo_name="Richmond",
        parent_geo_code="933",
        dguid="2021A00055915015",
        census_profile_flow="DF_CSD",
        lat=49.1666,
        lng=-123.1336,
        bc_gate_text="Richmond, BC",
    ),
    StatCanGeoConfig(
        geo_code="5915004",
        geo_level="CSD",
        geo_name="Surrey",
        parent_geo_code="933",
        dguid="2021A00055915004",
        census_profile_flow="DF_CSD",
        lat=49.1913,
        lng=-122.849,
        bc_gate_text="Surrey, BC",
    ),
    StatCanGeoConfig(
        geo_code="5915051",
        geo_level="CSD",
        geo_name="North Vancouver",
        parent_geo_code="933",
        dguid="2021A00055915051",
        census_profile_flow="DF_CSD",
        lat=49.32,
        lng=-123.073,
        bc_gate_text="North Vancouver, BC",
    ),
]

CATEGORY_BUSINESS_NAICS = {
    "recovery_contrast_therapy": {
        "code": "8121",
        "label": "Personal care services",
        "confidence": 0.9,
    },
    "fitness_movement": {
        "code": "7139",
        "label": "Other amusement and recreation industries",
        "confidence": 0.88,
    },
    "mind_meditation": {
        "code": "6116",
        "label": "Other schools and instruction",
        "confidence": 0.84,
    },
    "spa_thermal": {
        "code": "8121",
        "label": "Personal care services",
        "confidence": 0.9,
    },
    "nutrition_longevity": {
        "code": "6213",
        "label": "Offices of other health practitioners",
        "confidence": 0.82,
    },
    "allied_health": {
        "code": "6213",
        "label": "Offices of other health practitioners",
        "confidence": 0.88,
    },
    "womens_health": {
        "code": "6214",
        "label": "Out-patient care centres",
        "confidence": 0.78,
    },
    "preventive_diagnostic": {
        "code": "6215",
        "label": "Medical and diagnostic laboratories",
        "confidence": 0.86,
    },
    "mental_health": {
        "code": "6213",
        "label": "Offices of other health practitioners",
        "confidence": 0.76,
    },
    "community_social_wellness": {
        "code": "8134",
        "label": "Civic and social organizations",
        "confidence": 0.8,
    },
    "wellness_retail_product": {
        "code": "4561",
        "label": "Health and personal care retailers",
        "confidence": 0.86,
    },
}


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
    wds_base_url = STATCAN_WDS_BASE_URL

    def __init__(
        self,
        *,
        client: Any | None = None,
        fixture_path: Path | None = DEFAULT_FIXTURE_PATH,
        mode: FetchMode | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self.client = client
        self.fixture_path = fixture_path
        self.mode: FetchMode = mode or os.getenv("WR_STATCAN_WDS_MODE", "auto")  # type: ignore[assignment]
        self.cache_dir = cache_dir or _default_cache_dir()
        if self.mode not in {"auto", "fixture", "live"}:
            raise ValueError("WR_STATCAN_WDS_MODE must be one of auto, fixture, or live")

    def fetch(self) -> list[dict[str, Any]]:
        if self.mode == "fixture":
            return self._fixture_records(live_attempted=False, live_error=None)

        try:
            return self._fetch_live_normalized()
        except Exception as exc:
            if self.mode == "live" or self.fixture_path is None:
                raise
            return self._fixture_records(live_attempted=True, live_error=str(exc))

    def _fetch_live_normalized(self) -> list[dict[str, Any]]:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return _records_from_live_sources(client=self.client, cache_dir=self.cache_dir)

    def _fixture_records(
        self,
        *,
        live_attempted: bool,
        live_error: str | None,
    ) -> list[dict[str, Any]]:
        if self.fixture_path is None:
            raise RuntimeError("StatCan fixture_path is required for fixture fallback")
        payload = json.loads(self.fixture_path.read_text())
        shared_refs = payload.get("source_refs", [])
        records = payload.get("records", [])
        return [
            {
                **record,
                "fixture_recorded_at": payload.get("fixture_recorded_at"),
                "fixture_note": payload.get("fixture_note"),
                "demand_source": "statcan_wds_fixture",
                "demand_source_status": "fixture_fallback" if live_attempted else "fixture",
                "live_attempted": live_attempted,
                "live_error": live_error,
                "source_refs": [*shared_refs, *record.get("source_refs", [])],
            }
            for record in records
        ]

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
                "demand_source": raw.get("demand_source", "statcan_wds_live"),
                "demand_source_status": raw.get("demand_source_status", "live"),
                "live_attempted": bool(raw.get("live_attempted", False)),
                "live_error": raw.get("live_error"),
                "cache_status": raw.get("cache_status"),
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
        denominator_source_refs = _unique_refs(
            [*source_refs, *list(denominator.get("source_refs") or [])]
        )
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
            source_refs=denominator_source_refs,
            confidence_score=float(denominator.get("confidence_score", 0.8)),
            payload={
                "raw_payload_id": raw_payload_id,
                "fixture_note": raw.get("fixture_note"),
                "demand_source": raw.get("demand_source", "statcan_wds_live"),
                "demand_source_status": raw.get("demand_source_status", "live"),
                "live_attempted": bool(raw.get("live_attempted", False)),
                "live_error": raw.get("live_error"),
                "cache_status": raw.get("cache_status"),
                "source_table": denominator.get("source_table"),
                "source_vector": denominator.get("source_vector"),
                "source_coordinate": denominator.get("source_coordinate"),
                "source_naics_label": denominator.get("source_naics_label"),
                "source_metric": metric,
            },
        )


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str | int | float):
        raise TypeError(f"cannot convert {type(value).__name__} to float")
    return float(value)


def _records_from_live_sources(
    *,
    client: Any | None,
    cache_dir: Path,
) -> list[dict[str, Any]]:
    populations, population_cache_status, population_live_error = _fetch_population_by_geo(
        client=client,
        cache_dir=cache_dir,
        geographies=LIVE_GEOGRAPHIES,
    )
    business_rows, business_cache_status, business_live_error = _fetch_business_rows(
        client=client,
        cache_dir=cache_dir,
        geographies=LIVE_GEOGRAPHIES,
    )
    live_error = population_live_error or business_live_error
    cache_status = _combined_cache_status(population_cache_status, business_cache_status)
    now = _utc_seen_at()
    shared_refs = [
        SourceRef(
            source_name="statcan_wds",
            url="https://www.statcan.gc.ca/en/developers/wds",
            trust_tier="official",
            seen_at=now,
            source_record_id="wds",
            licence="Statistics Canada Open Licence",
        ).as_dict(),
    ]
    records: list[dict[str, Any]] = []
    for geography in LIVE_GEOGRAPHIES:
        population = populations.get(geography.geo_code)
        if population is None:
            raise RuntimeError(f"missing live Census Profile population for {geography.geo_code}")
        denominators = [
            {
                "metric": "population",
                "value": population["value"],
                "unit": "persons",
                "reference_period": str(population["reference_period"]),
                "confidence_score": 0.98,
                "source_refs": [population["source_ref"]],
                "source_table": "2021 Census Profile",
                "source_vector": None,
                "source_coordinate": population["dguid"],
                "source_naics_label": None,
            }
        ]
        for category, config in CATEGORY_BUSINESS_NAICS.items():
            key = (geography.geo_code, str(config["code"]))
            business = business_rows.get(key)
            if business is None:
                raise RuntimeError(
                    "missing live Business Counts row for "
                    f"{geography.geo_code} NAICS {config['code']}"
                )
            denominators.append(
                {
                    "metric": "business_count",
                    "category": category,
                    "naics_code": config["code"],
                    "value": business["value"],
                    "unit": "business locations with employees",
                    "reference_period": str(business["reference_period"]),
                    "confidence_score": float(str(config["confidence"])),
                    "source_refs": [business["source_ref"]],
                    "source_table": STATCAN_BUSINESS_COUNTS_TABLE_ID,
                    "source_vector": business["vector"],
                    "source_coordinate": business["coordinate"],
                    "source_naics_label": business["naics_label"],
                }
            )
        records.append(
            {
                "geo_code": geography.geo_code,
                "geo_level": geography.geo_level,
                "geo_name": geography.geo_name,
                "parent_geo_code": geography.parent_geo_code,
                "lat": geography.lat,
                "lng": geography.lng,
                "bc_gate_text": geography.bc_gate_text,
                "denominators": denominators,
                "demand_source": "statcan_wds_live",
                "demand_source_status": "live",
                "live_attempted": True,
                "live_error": live_error,
                "cache_status": cache_status,
                "source_refs": shared_refs,
                "confidence_score": 0.96,
            }
        )
    return records


def _fetch_population_by_geo(
    *,
    client: Any | None,
    cache_dir: Path,
    geographies: list[StatCanGeoConfig],
) -> tuple[dict[str, dict[str, Any]], str, str | None]:
    rows: dict[str, dict[str, Any]] = {}
    cache_statuses: list[str] = []
    live_error: str | None = None
    for flow in sorted({geography.census_profile_flow for geography in geographies}):
        flow_geographies = [
            geography for geography in geographies if geography.census_profile_flow == flow
        ]
        dguids = "+".join(geography.dguid for geography in flow_geographies)
        url = f"{STATCAN_CENSUS_PROFILE_BASE_URL}/STC_CP,{flow}/A5.{dguids}.1.1.1?format=csv"
        cache_key = _cache_key("census_profile", flow, dguids)
        payload, cache_status, error = _get_url_bytes(
            url,
            client=client,
            cache_path=cache_dir / f"{cache_key}.csv",
            accept="text/csv,application/json,*/*",
        )
        cache_statuses.append(cache_status)
        live_error = live_error or error
        source_ref = SourceRef(
            source_name="statcan_census_profile",
            url=url,
            trust_tier="official",
            seen_at=_utc_seen_at(),
            source_record_id=f"2021-profile-{flow}",
            licence="Statistics Canada Open Licence",
        ).as_dict()
        text = payload.decode("utf-8-sig")
        for row in csv.DictReader(io.StringIO(text)):
            geo_code = str(row.get("ALT_GEO_CODE") or "").strip()
            if not geo_code:
                continue
            rows[geo_code] = {
                "value": float(row["OBS_VALUE"]),
                "reference_period": row.get("TIME_PERIOD") or "2021",
                "dguid": row.get("REF_AREA") or row.get("GEO_DESC"),
                "source_ref": {
                    **source_ref,
                    "source_record_id": f"{source_ref['source_record_id']}:{geo_code}",
                },
            }
    return rows, _combined_cache_status(*cache_statuses), live_error


def _fetch_business_rows(
    *,
    client: Any | None,
    cache_dir: Path,
    geographies: list[StatCanGeoConfig],
) -> tuple[dict[tuple[str, str], dict[str, Any]], str, str | None]:
    payload, cache_status, live_error = _get_url_bytes(
        STATCAN_BUSINESS_COUNTS_CSV_URL,
        client=client,
        cache_path=cache_dir / "33101016-eng.zip",
        accept="application/zip,*/*",
    )
    dguid_to_geo_code = {geography.dguid: geography.geo_code for geography in geographies}
    wanted_naics = {str(config["code"]) for config in CATEGORY_BUSINESS_NAICS.values()}
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    with zipfile.ZipFile(io.BytesIO(payload)) as archive, archive.open(
        "33101016.csv"
    ) as raw_csv:
        text = io.TextIOWrapper(raw_csv, encoding="utf-8-sig")
        for row in csv.DictReader(text):
            geo_code = dguid_to_geo_code.get(str(row.get("DGUID") or ""))
            if not geo_code:
                continue
            if row.get("Employment size") != "Total, with employees":
                continue
            naics_code = _naics_code(
                row.get("North American Industry Classification System (NAICS)")
            )
            if naics_code not in wanted_naics:
                continue
            value = row.get("VALUE")
            if value in {None, ""}:
                continue
            rows[(geo_code, naics_code)] = {
                "value": float(str(value)),
                "reference_period": row.get("REF_DATE") or "2025-01",
                "vector": row.get("VECTOR"),
                "coordinate": row.get("COORDINATE"),
                "naics_label": row.get("North American Industry Classification System (NAICS)"),
                "source_ref": SourceRef(
                    source_name="statcan_business_counts",
                    url=STATCAN_BUSINESS_COUNTS_TABLE_URL,
                    trust_tier="official",
                    seen_at=_utc_seen_at(),
                    source_record_id=(
                        f"{STATCAN_BUSINESS_COUNTS_TABLE_ID}:"
                        f"{geo_code}:{naics_code}:{row.get('VECTOR')}"
                    ),
                    licence="Statistics Canada Open Licence",
                ).as_dict(),
            }
    return rows, cache_status, live_error


def _get_url_bytes(
    url: str,
    *,
    client: Any | None,
    cache_path: Path,
    accept: str,
) -> tuple[bytes, str, str | None]:
    max_age_seconds = int(float(os.getenv("WR_STATCAN_CACHE_TTL_HOURS", "168")) * 3600)
    if cache_path.exists() and time.time() - cache_path.stat().st_mtime <= max_age_seconds:
        return cache_path.read_bytes(), "cache_hit", None
    try:
        payload = _client_get_bytes(url, client=client, accept=accept)
        cache_path.write_bytes(payload)
        return payload, "live_fetch", None
    except Exception as exc:
        if cache_path.exists():
            return cache_path.read_bytes(), "cache_hit_after_live_error", str(exc)
        raise


def _client_get_bytes(url: str, *, client: Any | None, accept: str) -> bytes:
    if client is not None and hasattr(client, "get_bytes"):
        result = client.get_bytes(url, accept=accept)
        if not isinstance(result, bytes):
            raise TypeError("StatCan test client get_bytes must return bytes")
        return result
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "wellness-radar/0.1", "Accept": accept},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"StatCan HTTP {exc.code} for {url}: {body[:240]}") from exc


def _cache_key(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"statcan_{digest}"


def _default_cache_dir() -> Path:
    raw_root = Path(os.getenv("RAW_STORAGE_DIR", "/tmp/wellness-radar-raw"))
    return raw_root / "statcan"


def _naics_code(label: object) -> str:
    text = str(label or "")
    if "[" not in text or "]" not in text:
        return ""
    return text.rsplit("[", 1)[-1].split("]", 1)[0].strip()


def _combined_cache_status(*statuses: str) -> str:
    if any(status == "cache_hit_after_live_error" for status in statuses):
        return "cache_hit_after_live_error"
    if statuses and all(status == "cache_hit" for status in statuses):
        return "cache_hit"
    if any(status == "cache_hit" for status in statuses):
        return "mixed_live_cache"
    return "live_fetch"


def _utc_seen_at() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _unique_refs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for ref in refs:
        key = json.dumps(ref, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        unique.append(ref)
    return unique
