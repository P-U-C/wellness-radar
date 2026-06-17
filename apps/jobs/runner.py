from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any, Protocol

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from apps.api.app.config import settings
from apps.jobs.adapters.city_vancouver_licences import CityVancouverBusinessLicencesAdapter
from packages.geo.bc_gate import CanonicalGeoRecord, GeoGateResult, bc_gate
from packages.schemas.canonical import CanonicalOperator, SignalRecord, SourceEventRecord
from packages.shared.ids import content_hash, stable_id


class RunnerRepository(Protocol):
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

    def upsert_operator(self, operator: CanonicalOperator) -> None:
        ...

    def upsert_source_event(self, event: SourceEventRecord) -> None:
        ...

    def upsert_signal(self, signal: SignalRecord) -> None:
        ...

    def close(self) -> None:
        ...


@dataclass
class RunMetrics:
    records_fetched: int = 0
    records_persisted: int = 0
    records_rejected: int = 0
    error_count: int = 0
    error_message: str | None = None


class DatabaseRepository:
    def __init__(self, database_url: str | None = None) -> None:
        self.conn = psycopg.connect(database_url or settings.database_url, row_factory=dict_row)

    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> Any:
        return self.conn.execute(query, params)

    def rollback(self) -> None:
        self.conn.rollback()

    def ensure_source_rights(self, source_name: str) -> None:
        row = self.conn.execute(
            """
            SELECT source_name, rights_notes, enabled
            FROM source_registry
            WHERE source_name = %s
            """,
            (source_name,),
        ).fetchone()
        if not row:
            raise RuntimeError(f"source_registry row missing for {source_name}")
        if not row["rights_notes"] or "needs_review" not in row["rights_notes"]:
            raise RuntimeError(
                f"source_registry rights_notes missing needs_review for {source_name}"
            )

    def create_source_run(self, source_name: str) -> int:
        row = self.conn.execute(
            """
            INSERT INTO source_run (source_name, status, started_at)
            VALUES (%s, 'partial', now())
            RETURNING id
            """,
            (source_name,),
        ).fetchone()
        if row is None:
            raise RuntimeError("source_run insert did not return an id")
        self.conn.commit()
        return int(row["id"])

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
        self.conn.execute(
            """
            UPDATE source_run
            SET
              status = %s::source_run_status,
              completed_at = now(),
              records_fetched = %s,
              records_persisted = %s,
              records_rejected = %s,
              error_count = %s,
              error_message = %s
            WHERE id = %s
            """,
            (
                status,
                records_fetched,
                records_persisted,
                records_rejected,
                error_count,
                error_message,
                run_id,
            ),
        )
        self.conn.commit()

    def upsert_raw_payload(
        self, source_name: str, source_record_id: str, raw: dict[str, Any]
    ) -> str:
        digest = content_hash(raw)
        raw_payload_id = stable_id("raw", source_name, source_record_id, digest[:12])
        self.conn.execute(
            """
            INSERT INTO raw_payload (
              id, source_name, source_record_id, content_hash, raw_json
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
              fetched_at = now(),
              raw_json = EXCLUDED.raw_json
            """,
            (raw_payload_id, source_name, source_record_id, digest, Jsonb(raw)),
        )
        return raw_payload_id

    def write_rejection(
        self,
        record: CanonicalGeoRecord,
        result: GeoGateResult,
        raw_payload_id: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO rejected_record (source_name, reason, raw_payload_id, raw)
            VALUES (%s, %s, %s, %s)
            """,
            (
                record.source_name,
                result.reason or "bc_gate rejected record",
                raw_payload_id,
                Jsonb(record.raw),
            ),
        )

    def upsert_operator(self, operator: CanonicalOperator) -> None:
        self.conn.execute(
            """
            INSERT INTO "operator" (
              id,
              name,
              normalized_name,
              categories,
              status,
              address,
              municipality,
              neighborhood,
              geom,
              licence_ref,
              source_refs,
              confidence_score
            )
            VALUES (
              %s,
              %s,
              %s,
              %s,
              %s::operator_status,
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
              %s
            )
            ON CONFLICT (id) DO UPDATE SET
              name = EXCLUDED.name,
              normalized_name = EXCLUDED.normalized_name,
              categories = EXCLUDED.categories,
              status = EXCLUDED.status,
              address = EXCLUDED.address,
              municipality = EXCLUDED.municipality,
              neighborhood = EXCLUDED.neighborhood,
              geom = EXCLUDED.geom,
              licence_ref = EXCLUDED.licence_ref,
              source_refs = EXCLUDED.source_refs,
              confidence_score = EXCLUDED.confidence_score,
              last_seen_at = now()
            """,
            (
                operator.id,
                operator.name,
                operator.normalized_name,
                operator.categories,
                operator.status,
                operator.address,
                operator.municipality,
                operator.neighborhood,
                operator.lng,
                operator.lat,
                operator.lng,
                operator.lat,
                operator.licence_ref,
                Jsonb(operator.source_refs),
                operator.confidence_score,
            ),
        )

    def upsert_source_event(self, event: SourceEventRecord) -> None:
        self.conn.execute(
            """
            INSERT INTO source_event (
              id,
              source_name,
              raw_payload_id,
              source_record_id,
              event_type,
              entity_type,
              entity_id,
              title,
              occurred_at,
              trust_tier,
              geom,
              source_refs,
              confidence_score,
              payload
            )
            VALUES (
              %s,
              %s,
              %s,
              %s,
              %s,
              %s,
              %s,
              %s,
              %s,
              %s::trust_tier,
              CASE WHEN %s::double precision IS NULL OR %s::double precision IS NULL
                THEN NULL
                ELSE ST_SetSRID(
                  ST_MakePoint(%s::double precision, %s::double precision),
                  4326
                )::geography
              END,
              %s,
              %s,
              %s
            )
            ON CONFLICT (id) DO UPDATE SET
              raw_payload_id = EXCLUDED.raw_payload_id,
              title = EXCLUDED.title,
              occurred_at = EXCLUDED.occurred_at,
              geom = EXCLUDED.geom,
              source_refs = EXCLUDED.source_refs,
              confidence_score = EXCLUDED.confidence_score,
              payload = EXCLUDED.payload
            """,
            (
                event.id,
                event.source_name,
                event.raw_payload_id,
                event.source_record_id,
                event.event_type,
                event.entity_type,
                event.entity_id,
                event.title,
                event.occurred_at,
                event.trust_tier,
                event.lng,
                event.lat,
                event.lng,
                event.lat,
                Jsonb(event.source_refs),
                event.confidence_score,
                Jsonb(event.payload),
            ),
        )

    def upsert_signal(self, signal: SignalRecord) -> None:
        self.conn.execute(
            """
            INSERT INTO signal (
              id,
              type,
              severity,
              title,
              summary,
              why_it_matters,
              source_name,
              source_url,
              trust_tier,
              occurred_at,
              geom,
              related_operator_id,
              source_event_ids,
              raw_payload_id,
              source_refs,
              confidence_score
            )
            VALUES (
              %s,
              %s,
              %s::signal_severity,
              %s,
              %s,
              %s,
              %s,
              %s,
              %s::trust_tier,
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
            ON CONFLICT (id) DO UPDATE SET
              title = EXCLUDED.title,
              summary = EXCLUDED.summary,
              why_it_matters = EXCLUDED.why_it_matters,
              occurred_at = EXCLUDED.occurred_at,
              geom = EXCLUDED.geom,
              related_operator_id = EXCLUDED.related_operator_id,
              source_event_ids = EXCLUDED.source_event_ids,
              raw_payload_id = EXCLUDED.raw_payload_id,
              source_refs = EXCLUDED.source_refs,
              confidence_score = EXCLUDED.confidence_score
            """,
            (
                signal.id,
                signal.type,
                signal.severity,
                signal.title,
                signal.summary,
                signal.why_it_matters,
                signal.source_name,
                signal.source_url,
                signal.trust_tier,
                signal.occurred_at,
                signal.lng,
                signal.lat,
                signal.lng,
                signal.lat,
                signal.related_operator_id,
                signal.source_event_ids,
                signal.raw_payload_id,
                Jsonb(signal.source_refs),
                signal.confidence_score,
            ),
        )

    def close(self) -> None:
        self.conn.commit()
        self.conn.close()


class InMemoryRepository:
    def __init__(self) -> None:
        self.raw_payloads: dict[str, dict[str, Any]] = {}
        self.operators: dict[str, CanonicalOperator] = {}
        self.source_events: dict[str, SourceEventRecord] = {}
        self.signals: dict[str, SignalRecord] = {}
        self.rejected: list[tuple[CanonicalGeoRecord, GeoGateResult, str]] = []
        self.source_runs: dict[int, dict[str, Any]] = {}
        self._run_id = 0

    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> Any:
        raise RuntimeError("in-memory repository has no PostGIS boundary table")

    def ensure_source_rights(self, source_name: str) -> None:
        if source_name != CityVancouverBusinessLicencesAdapter.name:
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
        digest = content_hash(raw)
        raw_payload_id = stable_id("raw", source_name, source_record_id, digest[:12])
        self.raw_payloads[raw_payload_id] = raw
        return raw_payload_id

    def write_rejection(
        self,
        record: CanonicalGeoRecord,
        result: GeoGateResult,
        raw_payload_id: str,
    ) -> None:
        self.rejected.append((record, result, raw_payload_id))

    def upsert_operator(self, operator: CanonicalOperator) -> None:
        self.operators[operator.id] = operator

    def upsert_source_event(self, event: SourceEventRecord) -> None:
        self.source_events[event.id] = event

    def upsert_signal(self, signal: SignalRecord) -> None:
        self.signals[signal.id] = signal

    def close(self) -> None:
        return None

    def rollback(self) -> None:
        return None


def run_adapter(adapter: Any, repository: RunnerRepository | None = None) -> RunMetrics:
    repo = repository or DatabaseRepository()
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
            operators = adapter.normalize(raw, raw_payload_id)
            for operator in operators:
                geo_record = _geo_record(operator, raw)
                if adapter.geo_aware:
                    gate = bc_gate(geo_record, repo)
                    if not gate.passes:
                        repo.write_rejection(geo_record, gate, raw_payload_id)
                        metrics.records_rejected += 1
                        continue

                event = source_event_from_operator(operator)
                signal = signal_from_operator(operator, event)
                repo.upsert_operator(operator)
                repo.upsert_source_event(event)
                repo.upsert_signal(signal)
                metrics.records_persisted += 1

        status = "success" if metrics.error_count == 0 else "partial"
        repo.complete_source_run(
            run_id,
            status=status,
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
            if hasattr(repo, "rollback"):
                repo.rollback()
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


def _geo_record(operator: CanonicalOperator, raw: dict[str, Any]) -> CanonicalGeoRecord:
    text = " ".join(
        str(value)
        for value in [
            operator.name,
            operator.address,
            operator.municipality,
            operator.province,
            raw.get("businesstype"),
            raw.get("businesssubtype"),
        ]
        if value
    )
    return CanonicalGeoRecord(
        source_name=operator.source_name,
        title=operator.name,
        address=operator.address,
        municipality=operator.municipality,
        province=operator.province,
        country=operator.country,
        lat=operator.lat,
        lng=operator.lng,
        text=text,
        statcan_geo_code=None,
        raw=raw,
    )


def source_event_from_operator(operator: CanonicalOperator) -> SourceEventRecord:
    event_type = "licence_closed" if operator.status == "closed" else "licence_active"
    event_id = stable_id("evt", operator.source_name, operator.source_record_id, event_type)
    return SourceEventRecord(
        id=event_id,
        source_name=operator.source_name,
        raw_payload_id=operator.raw_payload_id,
        source_record_id=operator.source_record_id,
        event_type=event_type,
        entity_type="operator",
        entity_id=operator.id,
        title=f"{operator.name} business licence {operator.status}",
        occurred_at=operator.occurred_at,
        trust_tier="official",
        lat=operator.lat,
        lng=operator.lng,
        source_refs=operator.source_refs,
        confidence_score=operator.confidence_score,
        payload=operator.payload,
    )


def signal_from_operator(operator: CanonicalOperator, event: SourceEventRecord) -> SignalRecord:
    signal_id = stable_id("sig", operator.source_name, operator.source_record_id, event.event_type)
    category_label = operator.categories[0].replace("_", " ")
    return SignalRecord(
        id=signal_id,
        type="licence_status",
        severity="info",
        title=f"City licence signal: {operator.name}",
        summary=(
            f"{operator.name} is listed as {operator.status} "
            "in City of Vancouver business licences."
        ),
        why_it_matters=(
            f"Adds source-backed evidence for the {category_label} operator map in Vancouver."
        ),
        source_name=operator.source_name,
        source_url=operator.source_url,
        trust_tier="official",
        occurred_at=operator.occurred_at,
        lat=operator.lat,
        lng=operator.lng,
        related_operator_id=operator.id,
        source_event_ids=[event.id],
        raw_payload_id=operator.raw_payload_id,
        source_refs=operator.source_refs,
        confidence_score=operator.confidence_score,
    )


def adapter_for_name(name: str, limit: int) -> Any:
    if name in {"city_vancouver_licences", CityVancouverBusinessLicencesAdapter.name}:
        return CityVancouverBusinessLicencesAdapter(limit=limit)
    raise ValueError(f"unknown adapter {name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "adapter",
        choices=["city_vancouver_licences", "city_vancouver_business_licences"],
    )
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    metrics = run_adapter(adapter_for_name(args.adapter, args.limit))
    print(
        {
            "fetched": metrics.records_fetched,
            "persisted": metrics.records_persisted,
            "rejected": metrics.records_rejected,
            "errors": metrics.error_count,
        }
    )


if __name__ == "__main__":
    main()
