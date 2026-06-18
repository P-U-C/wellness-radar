from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from psycopg.types.json import Jsonb

from apps.jobs.runner import DatabaseRepository, RunMetrics

DEFAULT_TRENDS_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "peer_city_trends.json"


@dataclass(frozen=True)
class TrendRecord:
    term: str
    city: str
    geography_code: str | None
    growth_class: str
    series: list[dict[str, Any]]
    source_name: str
    source_refs: list[dict[str, Any]]
    confidence_score: float
    is_stub: bool
    methodology: str


class TrendProvider(Protocol):
    source_name: str

    def fetch(self) -> list[TrendRecord]:
        ...


class FixturePeerCityTrendProvider:
    source_name = "peer_city_trends_fixture"

    def __init__(self, fixture_path: Path = DEFAULT_TRENDS_FIXTURE) -> None:
        self.fixture_path = fixture_path

    def fetch(self) -> list[TrendRecord]:
        payload = json.loads(self.fixture_path.read_text())
        records: list[TrendRecord] = []
        source_refs = payload["source_refs"]
        methodology = payload["methodology"]
        for term, city_series in payload["series"].items():
            for city, values in city_series.items():
                series = [
                    {"period": f"w{index + 1:02d}", "value": int(value)}
                    for index, value in enumerate(values)
                ]
                records.append(
                    TrendRecord(
                        term=term,
                        city=city,
                        geography_code=_city_code(city),
                        growth_class=_growth_class(values),
                        series=series,
                        source_name=self.source_name,
                        source_refs=source_refs,
                        confidence_score=0.62,
                        is_stub=True,
                        methodology=methodology,
                    )
                )
        return records


class GoogleTrendsProvider:
    source_name = "google_trends"

    def fetch(self) -> list[TrendRecord]:
        raise RuntimeError(
            "Google Trends provider is not enabled. Use FixturePeerCityTrendProvider until "
            "API access and terms are reviewed."
        )


class TrendRepository(Protocol):
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

    def upsert_trend(self, record: TrendRecord) -> None:
        ...

    def close(self) -> None:
        ...


class DatabaseTrendRepository(DatabaseRepository):
    def upsert_trend(self, record: TrendRecord) -> None:
        self.conn.execute(
            """
            INSERT INTO trend (
              term,
              city,
              geography_code,
              growth_class,
              series,
              source_name,
              source_refs,
              confidence_score,
              is_stub,
              methodology
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (term, city) DO UPDATE SET
              geography_code = EXCLUDED.geography_code,
              growth_class = EXCLUDED.growth_class,
              series = EXCLUDED.series,
              source_name = EXCLUDED.source_name,
              fetched_at = now(),
              source_refs = EXCLUDED.source_refs,
              confidence_score = EXCLUDED.confidence_score,
              is_stub = EXCLUDED.is_stub,
              methodology = EXCLUDED.methodology,
              updated_at = now()
            """,
            (
                record.term,
                record.city,
                record.geography_code,
                record.growth_class,
                Jsonb(record.series),
                record.source_name,
                Jsonb(record.source_refs),
                record.confidence_score,
                record.is_stub,
                record.methodology,
            ),
        )


@dataclass
class InMemoryTrendRepository:
    trends: dict[tuple[str, str], TrendRecord] = field(default_factory=dict)
    raw_payloads: dict[str, dict[str, Any]] = field(default_factory=dict)
    source_runs: dict[int, dict[str, Any]] = field(default_factory=dict)
    _run_id: int = 0

    def ensure_source_rights(self, source_name: str) -> None:
        if source_name != FixturePeerCityTrendProvider.source_name:
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
        raw_payload_id = f"raw_{source_name}_{source_record_id}"
        self.raw_payloads[raw_payload_id] = raw
        return raw_payload_id

    def upsert_trend(self, record: TrendRecord) -> None:
        self.trends[(record.term, record.city)] = record

    def close(self) -> None:
        return None


def run_peer_city_trends(
    provider: TrendProvider | None = None,
    repository: TrendRepository | None = None,
) -> RunMetrics:
    provider = provider or FixturePeerCityTrendProvider()
    repo = repository or DatabaseTrendRepository()
    metrics = RunMetrics()
    run_id = 0
    try:
        repo.ensure_source_rights(provider.source_name)
        run_id = repo.create_source_run(provider.source_name)
        records = provider.fetch()
        metrics.records_fetched = len(records)
        repo.upsert_raw_payload(
            provider.source_name,
            "peer-city-trends",
            {"records": [record.__dict__ for record in records]},
        )
        for record in records:
            repo.upsert_trend(record)
            metrics.records_persisted += 1
        repo.complete_source_run(
            run_id,
            status="success",
            records_fetched=metrics.records_fetched,
            records_persisted=metrics.records_persisted,
            records_rejected=metrics.records_rejected,
            error_count=metrics.error_count,
            error_message=metrics.error_message,
        )
        return metrics
    except Exception as exc:
        metrics.error_count += 1
        metrics.error_message = str(exc)
        if run_id:
            repo.complete_source_run(
                run_id,
                status="failed",
                records_fetched=metrics.records_fetched,
                records_persisted=metrics.records_persisted,
                records_rejected=metrics.records_rejected,
                error_count=metrics.error_count,
                error_message=metrics.error_message,
            )
        raise
    finally:
        repo.close()


def _growth_class(values: list[int]) -> str:
    if not values:
        return "unknown"
    delta = values[-1] - values[0]
    if delta >= 35:
        return "breakout"
    if delta >= 20:
        return "rising"
    if delta >= 8:
        return "steady"
    return "flat"


def _city_code(city: str) -> str | None:
    codes = {
        "Vancouver": "CA-BC-Vancouver",
        "Toronto": "CA-ON-Toronto",
        "Seattle": "US-WA-Seattle",
        "Austin": "US-TX-Austin",
        "Melbourne": "AU-VIC-Melbourne",
    }
    return codes.get(city)
