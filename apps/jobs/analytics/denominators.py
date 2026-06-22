from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from psycopg.types.json import Jsonb

from apps.jobs.adapters.statcan_wds import (
    StatCanDenominator,
    StatCanGeography,
    StatCanWdsAdapter,
)
from apps.jobs.runner import DatabaseRepository, RunMetrics
from packages.geo.bc_gate import CanonicalGeoRecord, GeoGateResult, bc_gate


class DenominatorRepository(Protocol):
    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> Any:
        ...

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

    def write_rejection(
        self,
        record: CanonicalGeoRecord,
        result: GeoGateResult,
        raw_payload_id: str,
    ) -> None:
        ...

    def upsert_geography(
        self, geography: StatCanGeography, gate: GeoGateResult
    ) -> None:
        ...

    def upsert_denominator(self, denominator: StatCanDenominator) -> None:
        ...

    def close(self) -> None:
        ...


class DatabaseDenominatorRepository(DatabaseRepository):
    def upsert_geography(
        self, geography: StatCanGeography, gate: GeoGateResult
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO statcan_geography (
              geo_code,
              geo_level,
              geo_name,
              parent_geo_code,
              geom,
              source_name,
              source_refs,
              confidence_score,
              bc_gate_result,
              payload
            )
            VALUES (
              %s,
              %s,
              %s,
              %s,
              CASE WHEN %s::double precision IS NULL OR %s::double precision IS NULL
                THEN NULL
                ELSE ST_SetSRID(
                  ST_MakePoint(%s::double precision, %s::double precision),
                  4326
                )::geography
              END,
              %s,
              %s,
              %s,
              %s,
              %s
            )
            ON CONFLICT (geo_code) DO UPDATE SET
              geo_level = EXCLUDED.geo_level,
              geo_name = EXCLUDED.geo_name,
              parent_geo_code = EXCLUDED.parent_geo_code,
              geom = EXCLUDED.geom,
              source_refs = EXCLUDED.source_refs,
              confidence_score = EXCLUDED.confidence_score,
              bc_gate_result = EXCLUDED.bc_gate_result,
              payload = EXCLUDED.payload,
              updated_at = now()
            """,
            (
                geography.geo_code,
                geography.geo_level,
                geography.geo_name,
                geography.parent_geo_code,
                geography.lng,
                geography.lat,
                geography.lng,
                geography.lat,
                geography.source_name,
                Jsonb(geography.source_refs),
                geography.confidence_score,
                Jsonb(
                    {
                        "passes": gate.passes,
                        "reason": gate.reason,
                        "confidence": gate.confidence,
                    }
                ),
                Jsonb(geography.payload),
            ),
        )

    def upsert_denominator(self, denominator: StatCanDenominator) -> None:
        if denominator.payload.get("demand_source_status") == "live":
            self.conn.execute(
                """
                DELETE FROM statcan_denominator
                WHERE geo_code = %s
                  AND metric = %s
                  AND category IS NOT DISTINCT FROM %s
                  AND id <> %s
                  AND COALESCE(payload->>'demand_source_status', '') <> 'live'
                """,
                (
                    denominator.geo_code,
                    denominator.metric,
                    denominator.category,
                    denominator.id,
                ),
            )
        self.conn.execute(
            """
            INSERT INTO statcan_denominator (
              id,
              geo_code,
              geo_level,
              geo_name,
              metric,
              category,
              naics_code,
              value,
              unit,
              reference_period,
              source_name,
              source_refs,
              confidence_score,
              payload
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
              geo_level = EXCLUDED.geo_level,
              geo_name = EXCLUDED.geo_name,
              value = EXCLUDED.value,
              unit = EXCLUDED.unit,
              source_refs = EXCLUDED.source_refs,
              confidence_score = EXCLUDED.confidence_score,
              payload = EXCLUDED.payload,
              updated_at = now()
            """,
            (
                denominator.id,
                denominator.geo_code,
                denominator.geo_level,
                denominator.geo_name,
                denominator.metric,
                denominator.category,
                denominator.naics_code,
                denominator.value,
                denominator.unit,
                denominator.reference_period,
                denominator.source_name,
                Jsonb(denominator.source_refs),
                denominator.confidence_score,
                Jsonb(denominator.payload),
            ),
        )


@dataclass
class InMemoryDenominatorRepository:
    geographies: dict[str, StatCanGeography] = field(default_factory=dict)
    denominators: dict[str, StatCanDenominator] = field(default_factory=dict)
    rejected: list[tuple[CanonicalGeoRecord, GeoGateResult, str]] = field(default_factory=list)
    raw_payloads: dict[str, dict[str, Any]] = field(default_factory=dict)
    source_runs: dict[int, dict[str, Any]] = field(default_factory=dict)
    _run_id: int = 0

    def ensure_source_rights(self, source_name: str) -> None:
        if source_name != StatCanWdsAdapter.name:
            raise RuntimeError(f"source_registry row missing for {source_name}")

    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> Any:
        raise RuntimeError("in-memory denominator repository has no boundary table")

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
        self.source_runs[run_id] = {
            **self.source_runs[run_id],
            "status": status,
            "records_fetched": records_fetched,
            "records_persisted": records_persisted,
            "records_rejected": records_rejected,
            "error_count": error_count,
            "error_message": error_message,
        }

    def upsert_raw_payload(
        self, source_name: str, source_record_id: str, raw: dict[str, Any]
    ) -> str:
        raw_payload_id = f"raw_{source_name}_{source_record_id}"
        self.raw_payloads[raw_payload_id] = raw
        return raw_payload_id

    def write_rejection(
        self,
        record: CanonicalGeoRecord,
        result: GeoGateResult,
        raw_payload_id: str,
    ) -> None:
        self.rejected.append((record, result, raw_payload_id))

    def upsert_geography(
        self, geography: StatCanGeography, gate: GeoGateResult
    ) -> None:
        geography.payload["bc_gate"] = {
            "passes": gate.passes,
            "reason": gate.reason,
            "confidence": gate.confidence,
        }
        self.geographies[geography.geo_code] = geography

    def upsert_denominator(self, denominator: StatCanDenominator) -> None:
        self.denominators[denominator.id] = denominator

    def close(self) -> None:
        return None


def run_statcan_denominators(
    adapter: StatCanWdsAdapter | None = None,
    repository: DenominatorRepository | None = None,
) -> RunMetrics:
    adapter = adapter or StatCanWdsAdapter()
    repo = repository or DatabaseDenominatorRepository()
    metrics = RunMetrics()
    run_id = 0
    try:
        repo.ensure_source_rights(adapter.name)
        run_id = repo.create_source_run(adapter.name)
        raw_records = adapter.fetch()
        metrics.records_fetched = len(raw_records)
        for raw in raw_records:
            source_record_id = adapter.source_record_id(raw)
            raw_payload_id = repo.upsert_raw_payload(adapter.name, source_record_id, raw)
            geography, denominators = adapter.normalize(raw, raw_payload_id)
            gate_record = CanonicalGeoRecord(
                source_name=adapter.name,
                title=geography.geo_name,
                address=None,
                municipality=geography.geo_name if geography.geo_level == "CSD" else None,
                province="BC",
                country="CA",
                lat=geography.lat,
                lng=geography.lng,
                text=geography.bc_gate_text,
                statcan_geo_code=geography.geo_code,
                raw=raw,
            )
            gate = bc_gate(gate_record, repo)
            if not gate.passes:
                repo.write_rejection(gate_record, gate, raw_payload_id)
                metrics.records_rejected += 1
                continue
            repo.upsert_geography(geography, gate)
            for denominator in denominators:
                repo.upsert_denominator(denominator)
                metrics.records_persisted += 1
        repo.complete_source_run(
            run_id,
            status="success" if metrics.error_count == 0 else "partial",
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
