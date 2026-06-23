from __future__ import annotations

import json
import math
import os
import re
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Protocol
from urllib.parse import urlencode

import httpx
from psycopg.types.json import Jsonb

from apps.jobs.analytics.bundles import BUNDLE_TAXONOMY, BundleDefinition
from apps.jobs.runner import DatabaseRepository, RunMetrics
from packages.shared.ids import content_hash, slugify, stable_id
from packages.shared.provenance import source_ref

OSM_SOURCE_NAME = "osm_overpass_first_mover"
GDELT_SOURCE_NAME = "gdelt_doc"
GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "bundle_global_signal.json"
)
METHOD_VERSION = "r3_bundle_global_signal_v1"
SourceStatus = Literal["live", "cached", "fixture_fallback"]
FetchMode = Literal["auto", "fixture", "live"]

GENERIC_GDELT_TERMS = {
    "club",
    "community",
    "conditioning",
    "contrast",
    "group",
    "membership",
    "recovery",
    "restore",
    "retail",
    "training",
}


@dataclass(frozen=True)
class CityConfig:
    city: str
    population: int
    bbox: tuple[float, float, float, float]


CITY_CONFIGS: tuple[CityConfig, ...] = (
    CityConfig("Vancouver", 662_248, (49.198, -123.224, 49.316, -123.023)),
    CityConfig("Austin", 974_447, (30.098, -97.938, 30.516, -97.561)),
    CityConfig("New York", 8_804_190, (40.4774, -74.2591, 40.9176, -73.7004)),
    CityConfig("Los Angeles", 3_898_747, (33.7037, -118.6682, 34.3373, -118.1553)),
    CityConfig("London", 8_866_180, (51.2868, -0.5103, 51.6919, 0.334)),
    CityConfig("Berlin", 3_878_100, (52.3383, 13.0883, 52.6755, 13.7611)),
    CityConfig("Toronto", 2_794_356, (43.581, -79.6393, 43.8555, -79.115)),
)


@dataclass(frozen=True)
class FetchOutcome:
    source_name: str
    source_record_id: str
    source_status: SourceStatus
    payload: dict[str, Any]
    source_refs: list[dict[str, Any]]
    confidence_score: float
    source_error: str | None = None


@dataclass(frozen=True)
class FirstMoverCityRecord:
    bundle_id: str
    city: str
    count: int
    density: float
    ratio_vs_vancouver: float
    source_status: SourceStatus
    source_refs: list[dict[str, Any]]
    confidence_score: float
    source_error: str | None


@dataclass(frozen=True)
class BundleGlobalRecord:
    bundle_id: str
    worldwide_match: dict[str, Any]
    source_refs: list[dict[str, Any]]
    first_mover_cities: list[FirstMoverCityRecord]


class BundleGlobalRepository(Protocol):
    def ensure_source_rights(self, source_name: str) -> None:
        ...

    def create_source_run(self, source_name: str) -> int:
        ...

    def complete_source_run(
        self,
        run_id: int,
        *,
        status: str,
        records_fetched: int,
        records_persisted: int,
        records_rejected: int,
        error_count: int,
        error_message: str | None = None,
    ) -> None:
        ...

    def upsert_raw_payload(
        self, source_name: str, source_record_id: str, raw: dict[str, Any]
    ) -> str:
        ...

    def cached_raw_payload(self, source_name: str, source_record_id: str) -> dict[str, Any] | None:
        ...

    def bundles_for_global_signal(self) -> list[dict[str, Any]]:
        ...

    def replace_global_signals(self, records: Sequence[BundleGlobalRecord]) -> None:
        ...

    def close(self) -> None:
        ...


class DatabaseBundleGlobalRepository(DatabaseRepository):
    def cached_raw_payload(self, source_name: str, source_record_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT raw_json
            FROM raw_payload
            WHERE source_name = %s
              AND source_record_id = %s
              AND raw_json IS NOT NULL
            ORDER BY fetched_at DESC
            LIMIT 1
            """,
            (source_name, source_record_id),
        ).fetchone()
        payload = row["raw_json"] if row else None
        return payload if isinstance(payload, dict) else None

    def bundles_for_global_signal(self) -> list[dict[str, Any]]:
        return list(
            self.conn.execute(
                """
                SELECT id, label, slug, member_count, source_refs
                FROM bundle
                WHERE jsonb_array_length(source_refs) > 0
                ORDER BY bundle_score DESC, label ASC
                """
            ).fetchall()
        )

    def replace_global_signals(self, records: Sequence[BundleGlobalRecord]) -> None:
        bundle_ids = [record.bundle_id for record in records]
        if not bundle_ids:
            return
        self.conn.execute(
            "DELETE FROM bundle_first_mover_city WHERE bundle_id = ANY(%s)",
            (bundle_ids,),
        )
        self.conn.execute("DELETE FROM bundle_global WHERE bundle_id = ANY(%s)", (bundle_ids,))
        for record in records:
            self.conn.execute(
                """
                INSERT INTO bundle_global (bundle_id, worldwide_match, source_refs)
                VALUES (%s, %s, %s)
                ON CONFLICT (bundle_id) DO UPDATE SET
                  worldwide_match = EXCLUDED.worldwide_match,
                  source_refs = EXCLUDED.source_refs,
                  updated_at = now()
                """,
                (
                    record.bundle_id,
                    Jsonb(record.worldwide_match),
                    Jsonb(record.source_refs),
                ),
            )
            for city in record.first_mover_cities:
                self.conn.execute(
                    """
                    INSERT INTO bundle_first_mover_city (
                      bundle_id,
                      city,
                      count,
                      density,
                      ratio_vs_vancouver,
                      source_status,
                      source_refs,
                      confidence_score,
                      source_error
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (bundle_id, city) DO UPDATE SET
                      count = EXCLUDED.count,
                      density = EXCLUDED.density,
                      ratio_vs_vancouver = EXCLUDED.ratio_vs_vancouver,
                      source_status = EXCLUDED.source_status,
                      source_refs = EXCLUDED.source_refs,
                      confidence_score = EXCLUDED.confidence_score,
                      source_error = EXCLUDED.source_error,
                      updated_at = now()
                    """,
                    (
                        city.bundle_id,
                        city.city,
                        city.count,
                        city.density,
                        city.ratio_vs_vancouver,
                        city.source_status,
                        Jsonb(city.source_refs),
                        city.confidence_score,
                        city.source_error,
                    ),
                )


@dataclass
class InMemoryBundleGlobalRepository:
    bundles: list[dict[str, Any]]
    raw_payloads: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    source_runs: dict[int, dict[str, Any]] = field(default_factory=dict)
    global_records: dict[str, BundleGlobalRecord] = field(default_factory=dict)
    _run_id: int = 0

    def ensure_source_rights(self, source_name: str) -> None:
        if source_name not in {OSM_SOURCE_NAME, GDELT_SOURCE_NAME}:
            raise RuntimeError(f"source_registry row missing for {source_name}")

    def create_source_run(self, source_name: str) -> int:
        self._run_id += 1
        self.source_runs[self._run_id] = {"source_name": source_name, "status": "partial"}
        return self._run_id

    def complete_source_run(
        self,
        run_id: int,
        *,
        status: str,
        records_fetched: int,
        records_persisted: int,
        records_rejected: int,
        error_count: int,
        error_message: str | None = None,
    ) -> None:
        self.source_runs[run_id].update(
            {
                "status": status,
                "records_fetched": records_fetched,
                "records_persisted": records_persisted,
                "records_rejected": records_rejected,
                "error_count": error_count,
                "error_message": error_message,
            }
        )

    def upsert_raw_payload(
        self, source_name: str, source_record_id: str, raw: dict[str, Any]
    ) -> str:
        self.raw_payloads[(source_name, source_record_id)] = raw
        return stable_id("raw", source_name, source_record_id, content_hash(raw)[:12])

    def cached_raw_payload(self, source_name: str, source_record_id: str) -> dict[str, Any] | None:
        return self.raw_payloads.get((source_name, source_record_id))

    def bundles_for_global_signal(self) -> list[dict[str, Any]]:
        return self.bundles

    def replace_global_signals(self, records: Sequence[BundleGlobalRecord]) -> None:
        for record in records:
            self.global_records[record.bundle_id] = record

    def close(self) -> None:
        return None


class BundleGlobalSignalFetcher:
    def __init__(
        self,
        repository: BundleGlobalRepository,
        *,
        client: Any | None = None,
        fixture_path: Path = DEFAULT_FIXTURE_PATH,
        mode: FetchMode | None = None,
        now: datetime | None = None,
        window_days: int = 90,
        gdelt_rate_limit_seconds: float = 5.1,
    ) -> None:
        self.repository = repository
        # Keep the sweep moving: GDELT throttles hard and can hang for tens of seconds,
        # which serially blocks the fast Overpass first-mover fetches. A short default
        # timeout fails GDELT fast to its fixture fallback (in auto mode) while leaving
        # the sub-second Overpass calls unaffected. Tunable via WR_BUNDLE_GLOBAL_HTTP_TIMEOUT.
        http_timeout = float(os.getenv("WR_BUNDLE_GLOBAL_HTTP_TIMEOUT", "12"))
        self.client = client or httpx.Client(
            timeout=http_timeout,
            headers={"user-agent": "wellness-radar/0.1", "accept": "application/json,*/*"},
        )
        self.fixture = json.loads(fixture_path.read_text())
        self.mode: FetchMode = mode or os.getenv("WR_BUNDLE_GLOBAL_MODE", "auto")  # type: ignore[assignment]
        if self.mode not in {"auto", "fixture", "live"}:
            raise ValueError("WR_BUNDLE_GLOBAL_MODE must be one of auto, fixture, or live")
        self.now = _as_utc(now or datetime.now(timezone.utc))
        self.window_days = window_days
        self.gdelt_rate_limit_seconds = gdelt_rate_limit_seconds
        self._last_gdelt_request_at = 0.0
        self.fetch_counts: dict[str, int] = {GDELT_SOURCE_NAME: 0, OSM_SOURCE_NAME: 0}

    def signal_for_bundle(
        self, bundle: dict[str, Any], definition: BundleDefinition
    ) -> BundleGlobalRecord:
        gdelt = self._gdelt_timeline(definition)
        city_outcomes = [self._overpass_count(definition, city) for city in CITY_CONFIGS]
        cities = _city_records(
            bundle_id=str(bundle["id"]),
            outcomes=city_outcomes,
            local_vancouver_count=int(bundle.get("member_count") or 0),
        )
        worldwide_match = _worldwide_match(
            gdelt=gdelt,
            cities=cities,
            window_days=self.window_days,
        )
        source_refs = _unique_refs(
            [
                *gdelt.source_refs,
                *_flatten_refs(city.source_refs for city in cities),
                _method_ref(self.now),
            ]
        )
        worldwide_match["source_refs"] = source_refs
        return BundleGlobalRecord(
            bundle_id=str(bundle["id"]),
            worldwide_match=worldwide_match,
            source_refs=source_refs,
            first_mover_cities=cities,
        )

    def _gdelt_timeline(self, definition: BundleDefinition) -> FetchOutcome:
        query = _gdelt_query(definition)
        start = self.now - timedelta(days=self.window_days)
        params = {
            "query": query,
            "mode": "timelinevol",
            "format": "json",
            "startdatetime": _gdelt_timestamp(start),
            "enddatetime": _gdelt_timestamp(self.now),
        }
        url = f"{GDELT_DOC_URL}?{urlencode(params)}"
        source_record_id = stable_id(
            "gdelt",
            definition.slug,
            start.date().isoformat(),
            self.now.date().isoformat(),
            content_hash(params)[:12],
        )
        cached = self.repository.cached_raw_payload(GDELT_SOURCE_NAME, source_record_id)
        if cached is not None:
            return self._cached_outcome(GDELT_SOURCE_NAME, source_record_id, cached)
        if self.mode == "fixture":
            return self._gdelt_fixture(definition, source_record_id, url, "fixture mode requested")

        refs = [
            source_ref(
                source_name=GDELT_SOURCE_NAME,
                url=url,
                trust_tier="community",
                source_record_id=source_record_id,
                licence="GDELT Project terms",
                seen_at=_iso(self.now),
            )
        ]
        try:
            self._wait_for_gdelt()
            response = self.client.get(GDELT_DOC_URL, params=params)
            _raise_for_status(response)
            payload = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError("GDELT response was not a JSON object")
            raw = {
                "source_status": "live",
                "query": query,
                "params": params,
                "response": payload,
                "source_refs": refs,
                "methodology_version": METHOD_VERSION,
            }
            self.repository.upsert_raw_payload(GDELT_SOURCE_NAME, source_record_id, raw)
            self.fetch_counts[GDELT_SOURCE_NAME] += 1
            return FetchOutcome(
                source_name=GDELT_SOURCE_NAME,
                source_record_id=source_record_id,
                source_status="live",
                payload=payload,
                source_refs=refs,
                confidence_score=_gdelt_confidence(payload, "live"),
            )
        except Exception as exc:
            if self.mode == "live":
                raise
            return self._gdelt_fixture(definition, source_record_id, url, str(exc))

    def _gdelt_fixture(
        self,
        definition: BundleDefinition,
        source_record_id: str,
        url: str,
        source_error: str,
    ) -> FetchOutcome:
        values = self.fixture.get("gdelt", {}).get(definition.slug, [])
        payload = {
            "query_details": {"title": _gdelt_query(definition), "date_resolution": "fixture"},
            "timeline": [
                {
                    "series": "Volume Intensity",
                    "data": [
                        {"date": f"fixture_{index + 1:02d}", "value": float(value)}
                        for index, value in enumerate(values)
                    ],
                }
            ],
        }
        refs = [
            source_ref(
                source_name=GDELT_SOURCE_NAME,
                url=url,
                trust_tier="community",
                source_record_id=source_record_id,
                licence="GDELT Project terms",
                seen_at=str(self.fixture.get("fixture_recorded_at") or _iso(self.now)),
            )
        ]
        raw = {
            "source_status": "fixture_fallback",
            "fixture_path": str(DEFAULT_FIXTURE_PATH),
            "fixture_note": self.fixture.get("fixture_note"),
            "live_error": source_error,
            "response": payload,
            "source_refs": refs,
            "methodology_version": METHOD_VERSION,
        }
        self.repository.upsert_raw_payload(GDELT_SOURCE_NAME, source_record_id, raw)
        self.fetch_counts[GDELT_SOURCE_NAME] += 1
        return FetchOutcome(
            source_name=GDELT_SOURCE_NAME,
            source_record_id=source_record_id,
            source_status="fixture_fallback",
            payload=payload,
            source_refs=refs,
            confidence_score=_gdelt_confidence(payload, "fixture_fallback"),
            source_error=source_error,
        )

    def _overpass_count(self, definition: BundleDefinition, city: CityConfig) -> FetchOutcome:
        query = _overpass_query(definition, city)
        url = f"{OVERPASS_URL}?{urlencode({'data': query})}"
        source_record_id = stable_id(
            "osm_first_mover",
            definition.slug,
            city.city,
            content_hash(query)[:12],
        )
        cached = self.repository.cached_raw_payload(OSM_SOURCE_NAME, source_record_id)
        if cached is not None:
            return self._cached_outcome(OSM_SOURCE_NAME, source_record_id, cached)
        if self.mode == "fixture":
            return self._overpass_fixture(
                definition,
                city,
                source_record_id,
                url,
                "fixture mode requested",
            )

        refs = [
            source_ref(
                source_name=OSM_SOURCE_NAME,
                url=url,
                trust_tier="community",
                source_record_id=source_record_id,
                licence="Open Database License",
                seen_at=_iso(self.now),
            )
        ]
        try:
            response = self.client.post(OVERPASS_URL, data={"data": query})
            _raise_for_status(response)
            payload = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError("Overpass response was not a JSON object")
            count = _parse_overpass_count(payload)
            raw = {
                "source_status": "live",
                "query": query,
                "response": payload,
                "count": count,
                "city": city.city,
                "population": city.population,
                "source_refs": refs,
                "methodology_version": METHOD_VERSION,
            }
            self.repository.upsert_raw_payload(OSM_SOURCE_NAME, source_record_id, raw)
            self.fetch_counts[OSM_SOURCE_NAME] += 1
            return FetchOutcome(
                source_name=OSM_SOURCE_NAME,
                source_record_id=source_record_id,
                source_status="live",
                payload={"count": count, "query": query, "city": city.city},
                source_refs=refs,
                confidence_score=0.74,
            )
        except Exception as exc:
            if self.mode == "live":
                raise
            return self._overpass_fixture(definition, city, source_record_id, url, str(exc))

    def _overpass_fixture(
        self,
        definition: BundleDefinition,
        city: CityConfig,
        source_record_id: str,
        url: str,
        source_error: str,
    ) -> FetchOutcome:
        count = int(self.fixture.get("osm_counts", {}).get(definition.slug, {}).get(city.city, 0))
        refs = [
            source_ref(
                source_name=OSM_SOURCE_NAME,
                url=url,
                trust_tier="community",
                source_record_id=source_record_id,
                licence="Open Database License",
                seen_at=str(self.fixture.get("fixture_recorded_at") or _iso(self.now)),
            )
        ]
        raw = {
            "source_status": "fixture_fallback",
            "fixture_path": str(DEFAULT_FIXTURE_PATH),
            "fixture_note": self.fixture.get("fixture_note"),
            "live_error": source_error,
            "query": _overpass_query(definition, city),
            "count": count,
            "city": city.city,
            "population": city.population,
            "source_refs": refs,
            "methodology_version": METHOD_VERSION,
        }
        self.repository.upsert_raw_payload(OSM_SOURCE_NAME, source_record_id, raw)
        self.fetch_counts[OSM_SOURCE_NAME] += 1
        return FetchOutcome(
            source_name=OSM_SOURCE_NAME,
            source_record_id=source_record_id,
            source_status="fixture_fallback",
            payload={"count": count, "query": raw["query"], "city": city.city},
            source_refs=refs,
            confidence_score=0.5,
            source_error=source_error,
        )

    def _cached_outcome(
        self, source_name: str, source_record_id: str, raw: dict[str, Any]
    ) -> FetchOutcome:
        raw_status = str(raw.get("source_status") or "live")
        source_status: SourceStatus = (
            "fixture_fallback" if raw_status == "fixture_fallback" else "cached"
        )
        refs = [ref for ref in raw.get("source_refs") or [] if isinstance(ref, dict)]
        payload = raw.get("response") if source_name == GDELT_SOURCE_NAME else raw
        if not isinstance(payload, dict):
            payload = {}
        confidence = (
            _gdelt_confidence(payload, source_status)
            if source_name == GDELT_SOURCE_NAME
            else (0.5 if source_status == "fixture_fallback" else 0.66)
        )
        if source_name == OSM_SOURCE_NAME and "count" not in payload:
            payload = {"count": _parse_overpass_count(payload), "response": payload}
        self.fetch_counts[source_name] += 1
        return FetchOutcome(
            source_name=source_name,
            source_record_id=source_record_id,
            source_status=source_status,
            payload=payload,
            source_refs=refs,
            confidence_score=confidence,
            source_error=raw.get("live_error") if source_status == "fixture_fallback" else None,
        )

    def _wait_for_gdelt(self) -> None:
        if self.gdelt_rate_limit_seconds <= 0:
            return
        elapsed = time.monotonic() - self._last_gdelt_request_at
        wait_seconds = self.gdelt_rate_limit_seconds - elapsed
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        self._last_gdelt_request_at = time.monotonic()


def run_bundle_global_signal(
    repository: BundleGlobalRepository | None = None,
    *,
    client: Any | None = None,
    now: datetime | None = None,
    window_days: int = 90,
    mode: FetchMode | None = None,
    gdelt_rate_limit_seconds: float = 5.1,
) -> RunMetrics:
    repo = repository or DatabaseBundleGlobalRepository()
    metrics = RunMetrics()
    source_runs: dict[str, int] = {}
    try:
        for source_name in (GDELT_SOURCE_NAME, OSM_SOURCE_NAME):
            repo.ensure_source_rights(source_name)
            source_runs[source_name] = repo.create_source_run(source_name)
        fetcher = BundleGlobalSignalFetcher(
            repo,
            client=client,
            now=now,
            window_days=window_days,
            mode=mode,
            gdelt_rate_limit_seconds=gdelt_rate_limit_seconds,
        )
        records: list[BundleGlobalRecord] = []
        for bundle in repo.bundles_for_global_signal():
            definition = _definition_for_bundle(bundle)
            if definition is None:
                continue
            records.append(fetcher.signal_for_bundle(bundle, definition))
        repo.replace_global_signals(records)
        metrics.records_fetched = sum(fetcher.fetch_counts.values())
        metrics.records_persisted = len(records) + sum(
            len(record.first_mover_cities) for record in records
        )
        _complete_source_runs(repo, source_runs, fetcher, records, status="success")
        return metrics
    except Exception as exc:
        metrics.error_count += 1
        metrics.error_message = str(exc)
        if hasattr(repo, "rollback"):
            repo.rollback()
        _complete_source_runs(repo, source_runs, None, [], status="failed", error_message=str(exc))
        raise
    finally:
        repo.close()


def _complete_source_runs(
    repo: BundleGlobalRepository,
    source_runs: dict[str, int],
    fetcher: BundleGlobalSignalFetcher | None,
    records: Sequence[BundleGlobalRecord],
    *,
    status: str,
    error_message: str | None = None,
) -> None:
    for source_name, run_id in source_runs.items():
        fetched = fetcher.fetch_counts[source_name] if fetcher else 0
        persisted = 0
        if source_name == GDELT_SOURCE_NAME:
            persisted = len(records)
        elif source_name == OSM_SOURCE_NAME:
            persisted = sum(len(record.first_mover_cities) for record in records)
        repo.complete_source_run(
            run_id,
            status=status,
            records_fetched=fetched,
            records_persisted=persisted,
            records_rejected=0,
            error_count=1 if error_message else 0,
            error_message=error_message,
        )


def _definition_for_bundle(bundle: dict[str, Any]) -> BundleDefinition | None:
    bundle_id = str(bundle.get("id") or "")
    slug = str(bundle.get("slug") or "")
    label = str(bundle.get("label") or "")
    for definition in BUNDLE_TAXONOMY:
        if bundle_id == stable_id("bundle", definition.slug):
            return definition
        if slug == slugify(definition.slug).replace("_", "-"):
            return definition
        if label == definition.label:
            return definition
    return None


def _city_records(
    *,
    bundle_id: str,
    outcomes: Sequence[FetchOutcome],
    local_vancouver_count: int | None = None,
) -> list[FirstMoverCityRecord]:
    densities: dict[str, float] = {}
    counts: dict[str, int] = {}
    outcomes_by_city: dict[str, FetchOutcome] = {}
    for city, outcome in zip(CITY_CONFIGS, outcomes, strict=False):
        count = int(outcome.payload.get("count") or 0)
        # Vancouver is our home city: prefer our own authoritative mapped supply over the
        # Overpass/fixture peer-city path, which can stub Vancouver to 0 and break trust
        # (e.g. a bundle showing 68 mapped places yet "Vancouver: 0" in first-mover).
        if city.city == "Vancouver" and local_vancouver_count:
            count = int(local_vancouver_count)
        density = count / max(city.population / 1_000_000, 0.0001)
        counts[city.city] = count
        densities[city.city] = density
        outcomes_by_city[city.city] = outcome
    baseline_density = max(densities.get("Vancouver", 0.0), 0.1)
    records = []
    for city in CITY_CONFIGS:
        outcome = outcomes_by_city[city.city]
        density = densities[city.city]
        ratio = 1.0 if city.city == "Vancouver" else density / baseline_density
        is_local_vancouver = city.city == "Vancouver" and bool(local_vancouver_count)
        records.append(
            FirstMoverCityRecord(
                bundle_id=bundle_id,
                city=city.city,
                count=counts[city.city],
                density=round(density, 4),
                ratio_vs_vancouver=round(ratio, 4),
                source_status="live" if is_local_vancouver else outcome.source_status,
                source_refs=outcome.source_refs,
                confidence_score=round(_clamp(outcome.confidence_score), 4),
                source_error=outcome.source_error,
            )
        )
    return sorted(
        records,
        key=lambda record: (
            record.city == "Vancouver",
            -record.ratio_vs_vancouver,
            -record.density,
            record.city,
        ),
    )


def _worldwide_match(
    *,
    gdelt: FetchOutcome,
    cities: Sequence[FirstMoverCityRecord],
    window_days: int,
) -> dict[str, Any]:
    values = _gdelt_values(gdelt.payload)
    direction = _direction(values)
    value = _normalized_attention(values)
    non_vancouver = [city for city in cities if city.city != "Vancouver"]
    cities_with_supply = sum(1 for city in non_vancouver if city.count > 0)
    first_mover_ratio_count = sum(1 for city in non_vancouver if city.ratio_vs_vancouver >= 1.0)
    supply_spread = cities_with_supply / max(len(non_vancouver), 1)
    avg_ratio = _average([city.ratio_vs_vancouver for city in non_vancouver], default=0.0)
    if direction == "rising" and supply_spread >= 0.5 and first_mover_ratio_count >= 2:
        verdict = "global wave"
    elif direction == "rising" and supply_spread > 0:
        verdict = "emerging global attention"
    elif supply_spread >= 0.67 and direction in {"flat", "cooling"}:
        verdict = "established global category"
    elif supply_spread < 0.34 and value < 0.05:
        verdict = "local-only"
    else:
        verdict = "mixed global signal"
    source_status = _combined_status(
        [gdelt.source_status, *(city.source_status for city in cities)]
    )
    source_errors = [
        error
        for error in [gdelt.source_error, *(city.source_error for city in cities)]
        if error
    ]
    city_confidence = _average([city.confidence_score for city in cities], default=0.5)
    confidence = _average([gdelt.confidence_score, city_confidence], default=0.5)
    if source_status == "fixture_fallback":
        confidence *= 0.82
    return {
        "direction": direction,
        "value": value,
        "verdict": verdict,
        "source_status": source_status,
        "confidence_score": round(_clamp(confidence), 4),
        "window_days": window_days,
        "methodology_version": METHOD_VERSION,
        "components": {
            "gdelt_value": value,
            "gdelt_points": len(values),
            "cities_with_supply": cities_with_supply,
            "first_mover_cities_above_vancouver_density": first_mover_ratio_count,
            "supply_spread": round(supply_spread, 4),
            "average_ratio_vs_vancouver": round(avg_ratio, 4),
        },
        "source_errors": source_errors[:8],
    }


def _gdelt_query(definition: BundleDefinition) -> str:
    terms = [
        term
        for term in definition.keyword_terms
        if term not in GENERIC_GDELT_TERMS and len(term) > 2
    ][:5]
    if not terms:
        terms = [definition.label.lower()]
    encoded = [f'"{term}"' if " " in term else term for term in terms]
    if len(encoded) == 1:
        return encoded[0]
    return f"({' OR '.join(encoded)})"


def _overpass_query(definition: BundleDefinition, city: CityConfig) -> str:
    bbox = ",".join(str(value) for value in city.bbox)
    filters = []
    for tag in definition.tag_terms:
        key, separator, value = tag.partition("=")
        if separator and key and value:
            filters.append(f'  nwr["{_overpass_quote(key)}"="{_overpass_quote(value)}"]({bbox});')
    regex = _overpass_regex(definition.keyword_terms)
    if regex:
        filters.append(f'  nwr["name"~"{regex}",i]({bbox});')
        filters.append(f'  nwr["description"~"{regex}",i]({bbox});')
    if not filters:
        filters.append(f'  nwr["name"~"{_overpass_regex((definition.label,))}",i]({bbox});')
    return "\n".join(
        [
            "[out:json][timeout:25];",
            "(",
            *filters,
            ")->.matches;",
            ".matches out count;",
        ]
    )


def _overpass_regex(terms: Sequence[str]) -> str:
    cleaned = [term.strip().lower() for term in terms if len(term.strip()) > 2]
    if not cleaned:
        return ""
    escaped = [re.escape(term).replace("\\ ", " ") for term in cleaned]
    return "|".join(escaped).replace('"', '\\"')


def _overpass_quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _parse_overpass_count(payload: dict[str, Any]) -> int:
    elements = payload.get("elements")
    if not isinstance(elements, list):
        return 0
    for element in elements:
        if not isinstance(element, dict):
            continue
        tags = element.get("tags")
        if not isinstance(tags, dict):
            continue
        total = tags.get("total")
        if total is not None:
            return int(float(str(total)))
        nodes = int(float(str(tags.get("nodes") or 0)))
        ways = int(float(str(tags.get("ways") or 0)))
        relations = int(float(str(tags.get("relations") or 0)))
        return nodes + ways + relations
    return 0


def _gdelt_values(payload: dict[str, Any]) -> list[float]:
    timeline = payload.get("timeline")
    if not isinstance(timeline, list):
        return []
    values: list[float] = []
    for entry in timeline:
        if not isinstance(entry, dict):
            continue
        data = entry.get("data")
        if isinstance(data, list):
            for point in data:
                if isinstance(point, dict):
                    value = _optional_float(point.get("value"))
                    if value is not None:
                        values.append(value)
        else:
            value = _optional_float(entry.get("value"))
            if value is not None:
                values.append(value)
    return values


def _direction(values: Sequence[float]) -> str:
    if len(values) < 4:
        return "flat"
    third = max(len(values) // 3, 1)
    early = _average(values[:third], default=0.0)
    recent = _average(values[-third:], default=0.0)
    delta = recent - early
    if delta >= 0.02 and recent >= early * 1.15:
        return "rising"
    if delta <= -0.02 and recent <= early * 0.85:
        return "cooling"
    return "flat"


def _normalized_attention(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    third = max(len(values) // 3, 1)
    recent = _average(values[-third:], default=0.0)
    return round(_clamp(recent), 4)


def _gdelt_confidence(payload: dict[str, Any], source_status: SourceStatus) -> float:
    values = _gdelt_values(payload)
    base = 0.76 if values else 0.54
    if source_status == "cached":
        base *= 0.92
    if source_status == "fixture_fallback":
        base *= 0.68
    return round(_clamp(base), 4)


def _combined_status(statuses: Iterable[SourceStatus]) -> SourceStatus:
    status_list = list(statuses)
    if any(status == "fixture_fallback" for status in status_list):
        return "fixture_fallback"
    if any(status == "cached" for status in status_list):
        return "cached"
    return "live"


def _method_ref(now: datetime) -> dict[str, Any]:
    return source_ref(
        source_name="bundle_global_signal_method",
        url="apps/jobs/analytics/global_signal.py",
        trust_tier="informal",
        source_record_id=METHOD_VERSION,
        licence=None,
        seen_at=_iso(now),
    )


def _raise_for_status(response: Any) -> None:
    try:
        response.raise_for_status()
    except AttributeError:
        status_code = int(getattr(response, "status_code", 200))
        if status_code >= 400:
            raise RuntimeError(f"HTTP {status_code}: {getattr(response, 'text', '')}") from None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _gdelt_timestamp(value: datetime) -> str:
    return _as_utc(value).strftime("%Y%m%d%H%M%S")


def _iso(value: datetime) -> str:
    return _as_utc(value).isoformat().replace("+00:00", "Z")


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    if not isinstance(value, int | float | str):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _average(values: Iterable[float], *, default: float) -> float:
    cleaned = [value for value in values if value is not None]
    if not cleaned:
        return default
    return sum(cleaned) / len(cleaned)


def _flatten_refs(ref_groups: Iterable[Sequence[dict[str, Any]]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for group in ref_groups:
        refs.extend(ref for ref in group if isinstance(ref, dict))
    return refs


def _unique_refs(refs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    unique: list[dict[str, Any]] = []
    for ref in refs:
        key = (ref.get("source_name"), ref.get("source_record_id"), ref.get("url"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(ref)
    return unique


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
