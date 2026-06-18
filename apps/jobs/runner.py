from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from apps.api.app.config import settings
from apps.jobs.adapters.city_vancouver_licences import CityVancouverBusinessLicencesAdapter
from apps.jobs.adapters.manual_seed import ManualRecoverySeedAdapter
from apps.jobs.adapters.orgbook_bc import OrgBookBCEnrichmentAdapter
from apps.jobs.adapters.osm_overpass import OsmOverpassAdapter
from apps.jobs.adapters.rss import (
    BCGovHealthNewsAdapter,
    HealthCanadaRecallsAdapter,
    RssFeedAdapter,
)
from apps.jobs.enrichment.ai_signals import SignalEnrichment, SignalEnrichmentService
from apps.jobs.importers.people_csv import import_people_csv
from packages.geo.bc_gate import CanonicalGeoRecord, GeoGateResult, bc_gate
from packages.schemas.canonical import (
    CanonicalOperator,
    CanonicalOrganization,
    CanonicalPerson,
    SignalRecord,
    SourceEventRecord,
)
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


@dataclass(frozen=True)
class OperatorSnapshot:
    id: str
    name: str
    normalized_name: str
    website: str | None
    orgbook_id: str | None
    source_refs: list[dict[str, Any]]
    confidence_score: float


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
              completed_at = clock_timestamp(),
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
              categories = ARRAY(
                SELECT DISTINCT category
                FROM unnest("operator".categories || EXCLUDED.categories) AS category
              ),
              status = CASE
                WHEN EXCLUDED.status = 'unknown'::operator_status THEN "operator".status
                ELSE EXCLUDED.status
              END,
              address = COALESCE(EXCLUDED.address, "operator".address),
              municipality = COALESCE(EXCLUDED.municipality, "operator".municipality),
              neighborhood = COALESCE(EXCLUDED.neighborhood, "operator".neighborhood),
              geom = COALESCE(EXCLUDED.geom, "operator".geom),
              licence_ref = COALESCE(EXCLUDED.licence_ref, "operator".licence_ref),
              source_refs = (
                SELECT COALESCE(jsonb_agg(DISTINCT value), '[]'::jsonb)
                FROM jsonb_array_elements("operator".source_refs || EXCLUDED.source_refs) AS value
              ),
              confidence_score = GREATEST("operator".confidence_score, EXCLUDED.confidence_score),
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
              related_organization_id,
              related_person_ids,
              source_event_ids,
              raw_payload_id,
              ai_generated_fields,
              prompt_version,
              ai_model,
              ai_category_suggestions,
              ai_severity_suggestion,
              ai_confidence_score,
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
              %s,
              %s,
              %s,
              %s,
              %s,
              %s::signal_severity,
              %s,
              %s,
              %s
            )
            ON CONFLICT (id) DO UPDATE SET
              title = EXCLUDED.title,
              summary = COALESCE(signal.summary, EXCLUDED.summary),
              why_it_matters = COALESCE(signal.why_it_matters, EXCLUDED.why_it_matters),
              occurred_at = EXCLUDED.occurred_at,
              geom = EXCLUDED.geom,
              related_operator_id = EXCLUDED.related_operator_id,
              related_organization_id = EXCLUDED.related_organization_id,
              related_person_ids = EXCLUDED.related_person_ids,
              source_event_ids = EXCLUDED.source_event_ids,
              raw_payload_id = EXCLUDED.raw_payload_id,
              ai_generated_fields = CASE
                WHEN cardinality(signal.ai_generated_fields) = 0
                THEN EXCLUDED.ai_generated_fields
                ELSE signal.ai_generated_fields
              END,
              prompt_version = COALESCE(signal.prompt_version, EXCLUDED.prompt_version),
              ai_model = COALESCE(signal.ai_model, EXCLUDED.ai_model),
              ai_category_suggestions = CASE
                WHEN cardinality(signal.ai_category_suggestions) = 0
                THEN EXCLUDED.ai_category_suggestions
                ELSE signal.ai_category_suggestions
              END,
              ai_severity_suggestion = COALESCE(
                signal.ai_severity_suggestion,
                EXCLUDED.ai_severity_suggestion
              ),
              ai_confidence_score = COALESCE(
                signal.ai_confidence_score,
                EXCLUDED.ai_confidence_score
              ),
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
                signal.related_organization_id,
                signal.related_person_ids,
                signal.source_event_ids,
                signal.raw_payload_id,
                signal.ai_generated_fields,
                signal.prompt_version,
                signal.ai_model,
                signal.ai_category_suggestions,
                signal.ai_severity_suggestion,
                signal.ai_confidence_score,
                Jsonb(signal.source_refs),
                signal.confidence_score,
            ),
        )

    def find_operator_id(self, operator: CanonicalOperator) -> str | None:
        row = self.conn.execute(
            """
            SELECT id
            FROM "operator"
            WHERE normalized_name = %s
            ORDER BY last_seen_at DESC
            LIMIT 1
            """,
            (operator.normalized_name,),
        ).fetchone()
        return str(row["id"]) if row else None

    def list_operator_snapshots(self, limit: int = 250) -> list[OperatorSnapshot]:
        rows = self.conn.execute(
            """
            SELECT
              id,
              name,
              normalized_name,
              website,
              orgbook_id,
              source_refs,
              confidence_score
            FROM "operator"
            ORDER BY last_seen_at DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
        return [
            OperatorSnapshot(
                id=str(row["id"]),
                name=str(row["name"]),
                normalized_name=str(row["normalized_name"]),
                website=row["website"],
                orgbook_id=row["orgbook_id"],
                source_refs=list(row["source_refs"]),
                confidence_score=float(row["confidence_score"]),
            )
            for row in rows
        ]

    def upsert_organization(self, organization: CanonicalOrganization) -> None:
        self.conn.execute(
            """
            INSERT INTO organization (
              id,
              name,
              normalized_name,
              registry_id,
              orgbook_id,
              orgbook_match_status,
              orgbook_match_confidence,
              organization_type,
              website,
              social_links,
              source_refs,
              confidence_score
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
              name = EXCLUDED.name,
              normalized_name = EXCLUDED.normalized_name,
              registry_id = EXCLUDED.registry_id,
              orgbook_id = EXCLUDED.orgbook_id,
              orgbook_match_status = EXCLUDED.orgbook_match_status,
              orgbook_match_confidence = EXCLUDED.orgbook_match_confidence,
              organization_type = EXCLUDED.organization_type,
              website = COALESCE(EXCLUDED.website, organization.website),
              social_links = organization.social_links || EXCLUDED.social_links,
              source_refs = (
                SELECT COALESCE(jsonb_agg(DISTINCT value), '[]'::jsonb)
                FROM jsonb_array_elements(organization.source_refs || EXCLUDED.source_refs) AS value
              ),
              confidence_score = GREATEST(organization.confidence_score, EXCLUDED.confidence_score),
              last_seen_at = now()
            """,
            (
                organization.id,
                organization.name,
                organization.normalized_name,
                organization.registry_id,
                organization.orgbook_id,
                organization.orgbook_match_status,
                organization.orgbook_match_confidence,
                organization.organization_type,
                organization.website,
                Jsonb(organization.social_links),
                Jsonb(organization.source_refs),
                organization.confidence_score,
            ),
        )

    def update_operator_organization(
        self, operator_id: str, organization_id: str, orgbook_id: str | None
    ) -> None:
        self.conn.execute(
            """
            UPDATE "operator"
            SET organization_id = %s,
                orgbook_id = %s,
                last_seen_at = now()
            WHERE id = %s
            """,
            (organization_id, orgbook_id, operator_id),
        )

    def upsert_person(self, person: CanonicalPerson) -> None:
        self.conn.execute(
            """
            INSERT INTO person (
              id,
              name,
              normalized_name,
              roles,
              affiliations,
              public_profiles,
              confidence_score,
              source_refs
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
              name = EXCLUDED.name,
              normalized_name = EXCLUDED.normalized_name,
              roles = ARRAY(
                SELECT DISTINCT role
                FROM unnest(person.roles || EXCLUDED.roles) AS role
              ),
              affiliations = (
                SELECT COALESCE(jsonb_agg(DISTINCT value), '[]'::jsonb)
                FROM jsonb_array_elements(person.affiliations || EXCLUDED.affiliations) AS value
              ),
              public_profiles = person.public_profiles || EXCLUDED.public_profiles,
              confidence_score = GREATEST(person.confidence_score, EXCLUDED.confidence_score),
              source_refs = (
                SELECT COALESCE(jsonb_agg(DISTINCT value), '[]'::jsonb)
                FROM jsonb_array_elements(person.source_refs || EXCLUDED.source_refs) AS value
              ),
              last_seen_at = now()
            """,
            (
                person.id,
                person.name,
                person.normalized_name,
                person.roles,
                Jsonb(person.affiliations),
                Jsonb(person.public_profiles),
                person.confidence_score,
                Jsonb(person.source_refs),
            ),
        )

    def fetch_signals_for_enrichment(self, limit: int) -> list[dict[str, Any]]:
        return list(
            self.conn.execute(
                """
                SELECT
                  s.id,
                  s.type,
                  s.severity::text AS severity,
                  s.title,
                  s.summary,
                  s.why_it_matters,
                  s.source_name,
                  s.trust_tier::text AS trust_tier,
                  s.source_refs,
                  se.payload AS event_payload
                FROM signal s
                LEFT JOIN source_event se ON se.id = s.source_event_ids[1]
                WHERE cardinality(s.ai_generated_fields) = 0
                  AND s.source_event_ids <> '{}'
                ORDER BY s.ingested_at DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
        )

    def update_signal_ai_enrichment(
        self, signal_id: str, enrichment: SignalEnrichment
    ) -> None:
        self.conn.execute(
            """
            UPDATE signal
            SET summary = COALESCE(NULLIF(summary, ''), %s),
                why_it_matters = COALESCE(NULLIF(why_it_matters, ''), %s),
                ai_category_suggestions = %s,
                ai_severity_suggestion = %s::signal_severity,
                ai_confidence_score = %s,
                ai_generated_fields = %s,
                prompt_version = %s,
                ai_model = %s
            WHERE id = %s
            """,
            (
                enrichment.summary,
                enrichment.why_it_matters,
                enrichment.category_suggestions,
                enrichment.severity_suggestion,
                enrichment.confidence,
                enrichment.generated_fields,
                enrichment.prompt_version,
                enrichment.model_name,
                signal_id,
            ),
        )

    def close(self) -> None:
        self.conn.commit()
        self.conn.close()


class InMemoryRepository:
    def __init__(self) -> None:
        self.raw_payloads: dict[str, dict[str, Any]] = {}
        self.operators: dict[str, CanonicalOperator] = {}
        self.organizations: dict[str, CanonicalOrganization] = {}
        self.people: dict[str, CanonicalPerson] = {}
        self.source_events: dict[str, SourceEventRecord] = {}
        self.signals: dict[str, SignalRecord] = {}
        self.rejected: list[tuple[CanonicalGeoRecord, GeoGateResult, str]] = []
        self.source_runs: dict[int, dict[str, Any]] = {}
        self._run_id = 0

    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> Any:
        raise RuntimeError("in-memory repository has no PostGIS boundary table")

    def ensure_source_rights(self, source_name: str) -> None:
        known_sources = {
            CityVancouverBusinessLicencesAdapter.name,
            ManualRecoverySeedAdapter.name,
            OsmOverpassAdapter.name,
            OrgBookBCEnrichmentAdapter.name,
            RssFeedAdapter.name,
            BCGovHealthNewsAdapter.name,
            HealthCanadaRecallsAdapter.name,
            "manual_people_csv",
        }
        if source_name not in known_sources:
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

    def find_operator_id(self, operator: CanonicalOperator) -> str | None:
        for existing in self.operators.values():
            if existing.normalized_name == operator.normalized_name:
                return existing.id
        return None

    def upsert_source_event(self, event: SourceEventRecord) -> None:
        self.source_events[event.id] = event

    def upsert_signal(self, signal: SignalRecord) -> None:
        self.signals[signal.id] = signal

    def list_operator_snapshots(self, limit: int = 250) -> list[OperatorSnapshot]:
        snapshots = [
            OperatorSnapshot(
                id=operator.id,
                name=operator.name,
                normalized_name=operator.normalized_name,
                website=operator.source_url,
                orgbook_id=None,
                source_refs=operator.source_refs,
                confidence_score=operator.confidence_score,
            )
            for operator in self.operators.values()
        ]
        return snapshots[:limit]

    def upsert_organization(self, organization: CanonicalOrganization) -> None:
        self.organizations[organization.id] = organization

    def update_operator_organization(
        self, operator_id: str, organization_id: str, orgbook_id: str | None
    ) -> None:
        operator = self.operators[operator_id]
        operator.payload["organization_id"] = organization_id
        operator.payload["orgbook_id"] = orgbook_id

    def upsert_person(self, person: CanonicalPerson) -> None:
        self.people[person.id] = person

    def fetch_signals_for_enrichment(self, limit: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for signal in list(self.signals.values())[:limit]:
            if signal.ai_generated_fields:
                continue
            event_payload: dict[str, Any] = {}
            if signal.source_event_ids:
                event = self.source_events.get(signal.source_event_ids[0])
                event_payload = event.payload if event else {}
            rows.append(
                {
                    "id": signal.id,
                    "type": signal.type,
                    "severity": signal.severity,
                    "title": signal.title,
                    "summary": signal.summary,
                    "why_it_matters": signal.why_it_matters,
                    "source_name": signal.source_name,
                    "trust_tier": signal.trust_tier,
                    "source_refs": signal.source_refs,
                    "event_payload": event_payload,
                }
            )
        return rows

    def update_signal_ai_enrichment(
        self, signal_id: str, enrichment: SignalEnrichment
    ) -> None:
        signal = self.signals[signal_id]
        if not signal.summary:
            signal.summary = enrichment.summary
        if not signal.why_it_matters:
            signal.why_it_matters = enrichment.why_it_matters
        signal.ai_category_suggestions = enrichment.category_suggestions
        signal.ai_severity_suggestion = enrichment.severity_suggestion
        signal.ai_confidence_score = enrichment.confidence
        signal.ai_generated_fields = enrichment.generated_fields
        signal.prompt_version = enrichment.prompt_version
        signal.ai_model = enrichment.model_name

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

                if getattr(adapter, "dedupe_existing", False) and hasattr(repo, "find_operator_id"):
                    existing_id = repo.find_operator_id(operator)
                    if existing_id:
                        operator.id = existing_id

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
            raw.get("location_text"),
            raw.get("outlet"),
            raw.get("tags"),
            operator.payload,
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
    event_type = str(
        operator.payload.get(
            "event_type",
            "licence_closed" if operator.status == "closed" else "licence_active",
        )
    )
    event_id = stable_id("evt", operator.source_name, operator.source_record_id, event_type)
    title = operator.payload.get("event_title")
    if not title:
        if event_type.startswith("licence_"):
            title = f"{operator.name} business licence {operator.status}"
        else:
            title = f"{operator.name} observed by {operator.source_name}"
    trust_tier = _operator_trust_tier(operator)
    return SourceEventRecord(
        id=event_id,
        source_name=operator.source_name,
        raw_payload_id=operator.raw_payload_id,
        source_record_id=operator.source_record_id,
        event_type=event_type,
        entity_type="operator",
        entity_id=operator.id,
        title=str(title),
        occurred_at=operator.occurred_at,
        trust_tier=trust_tier,
        lat=operator.lat,
        lng=operator.lng,
        source_refs=operator.source_refs,
        confidence_score=operator.confidence_score,
        payload=operator.payload,
    )


def signal_from_operator(operator: CanonicalOperator, event: SourceEventRecord) -> SignalRecord:
    signal_type = str(operator.payload.get("signal_type", "licence_status"))
    signal_id = stable_id("sig", operator.source_name, operator.source_record_id, signal_type)
    category_label = operator.categories[0].replace("_", " ")
    title = operator.payload.get("signal_title")
    if not title:
        title = (
            f"City licence signal: {operator.name}"
            if signal_type == "licence_status"
            else f"Operator signal: {operator.name}"
        )
    summary = operator.payload.get("signal_summary")
    if not summary:
        summary = (
            f"{operator.name} is listed as {operator.status} "
            f"by {operator.source_name.replace('_', ' ')}."
        )
    trust_tier = _operator_trust_tier(operator)
    return SignalRecord(
        id=signal_id,
        type=signal_type,
        severity="info",
        title=str(title),
        summary=str(summary),
        why_it_matters=(
            f"Adds source-backed evidence for the {category_label} operator map in Vancouver."
        ),
        source_name=operator.source_name,
        source_url=operator.source_url,
        trust_tier=trust_tier,
        occurred_at=operator.occurred_at,
        lat=operator.lat,
        lng=operator.lng,
        related_operator_id=operator.id,
        source_event_ids=[event.id],
        raw_payload_id=operator.raw_payload_id,
        source_refs=operator.source_refs,
        confidence_score=operator.confidence_score,
    )


def _operator_trust_tier(operator: CanonicalOperator) -> str:
    if operator.payload.get("trust_tier"):
        return str(operator.payload["trust_tier"])
    if operator.source_refs:
        trust = operator.source_refs[0].get("trust_tier")
        if trust:
            return str(trust)
    return "official"


def run_event_adapter(adapter: Any, repository: RunnerRepository | None = None) -> RunMetrics:
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
            event_pairs = adapter.normalize(raw, raw_payload_id)
            for event, signal in event_pairs:
                if getattr(adapter, "text_gate", False):
                    gate_record = CanonicalGeoRecord(
                        source_name=event.source_name,
                        title=event.title,
                        address=None,
                        municipality=None,
                        province=None,
                        country="CA",
                        lat=None,
                        lng=None,
                        text=str(event.payload.get("bc_gate_text") or event.payload),
                        statcan_geo_code=None,
                        raw=raw,
                    )
                    gate = bc_gate(gate_record, repo)
                    if not gate.passes:
                        repo.write_rejection(gate_record, gate, raw_payload_id)
                        metrics.records_rejected += 1
                        continue
                repo.upsert_source_event(event)
                repo.upsert_signal(signal)
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


def run_orgbook_enrichment(
    adapter: OrgBookBCEnrichmentAdapter | None = None,
    repository: DatabaseRepository | InMemoryRepository | None = None,
    *,
    limit: int = 100,
) -> RunMetrics:
    adapter = adapter or OrgBookBCEnrichmentAdapter(limit=limit)
    repo = repository or DatabaseRepository()
    metrics = RunMetrics()
    run_id = 0
    try:
        repo.ensure_source_rights(adapter.name)
        run_id = repo.create_source_run(adapter.name)
        operators = repo.list_operator_snapshots(limit)
        metrics.records_fetched = len(operators)
        for operator in operators:
            payload = adapter.fetch_for_operator(operator.name)
            raw_payload_id = repo.upsert_raw_payload(adapter.name, operator.id, payload)
            match = adapter.match(operator.name, payload)
            organization = adapter.organization_for_operator(
                operator_id=operator.id,
                operator_name=operator.name,
                operator_website=operator.website,
                match=match,
            )
            repo.upsert_organization(organization)
            repo.update_operator_organization(operator.id, organization.id, match.orgbook_id)
            metrics.records_persisted += 1
            event = SourceEventRecord(
                id=stable_id("evt", adapter.name, operator.id, "orgbook_match"),
                source_name=adapter.name,
                raw_payload_id=raw_payload_id,
                source_record_id=operator.id,
                event_type="orgbook_match" if match.orgbook_id else "orgbook_unmatched",
                entity_type="organization",
                entity_id=organization.id,
                title=f"OrgBook BC {match.status}: {operator.name}",
                occurred_at=_utc_now(),
                trust_tier=adapter.trust_tier,
                lat=None,
                lng=None,
                source_refs=organization.source_refs,
                confidence_score=organization.confidence_score,
                payload={"operator_id": operator.id, "match_confidence": match.confidence},
            )
            repo.upsert_source_event(event)
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


def run_ai_enrichment(
    repository: DatabaseRepository | InMemoryRepository | None = None, *, limit: int = 100
) -> int:
    repo = repository or DatabaseRepository()
    return SignalEnrichmentService(repo).enrich_pending(limit)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def adapter_for_name(name: str, limit: int) -> Any:
    if name in {"city_vancouver_licences", CityVancouverBusinessLicencesAdapter.name}:
        return CityVancouverBusinessLicencesAdapter(limit=limit)
    if name in {"manual_seed", ManualRecoverySeedAdapter.name}:
        return ManualRecoverySeedAdapter(limit=limit)
    if name in {"osm", "osm_overpass", OsmOverpassAdapter.name}:
        return OsmOverpassAdapter(limit=limit)
    if name in {"local_rss", RssFeedAdapter.name}:
        return RssFeedAdapter(limit=limit)
    if name in {"bc_gov_news_rss", BCGovHealthNewsAdapter.name}:
        return BCGovHealthNewsAdapter(limit=limit)
    if name in {"health_canada_recalls", HealthCanadaRecallsAdapter.name}:
        return HealthCanadaRecallsAdapter(limit=limit)
    raise ValueError(f"unknown adapter {name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "adapter",
        choices=[
            "city_vancouver_licences",
            "city_vancouver_business_licences",
            "manual_seed",
            "osm_overpass",
            "local_rss",
            "bc_gov_news_rss",
            "health_canada_recalls",
            "orgbook_bc",
            "manual_people_csv",
            "ai_enrichment",
            "entity_resolution",
            "statcan_denominators",
            "opportunity_analytics",
            "peer_city_trends",
            "influence_scoring",
            "people_graph",
            "m2",
            "m3",
        ],
    )
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--people-csv", type=Path, default=None)
    args = parser.parse_args()

    if args.adapter in {"local_rss", "bc_gov_news_rss", "health_canada_recalls"}:
        metrics = run_event_adapter(adapter_for_name(args.adapter, args.limit))
        print(_metrics_dict(metrics))
        return
    if args.adapter == "orgbook_bc":
        metrics = run_orgbook_enrichment(limit=args.limit)
        print(_metrics_dict(metrics))
        return
    if args.adapter == "manual_people_csv":
        people_metrics = import_people_csv(DatabaseRepository(), path=args.people_csv)
        print(_metrics_dict(people_metrics))
        return
    if args.adapter == "ai_enrichment":
        print({"enriched": run_ai_enrichment(limit=args.limit)})
        return
    if args.adapter == "entity_resolution":
        from apps.jobs.analytics.entity_resolution import run_entity_resolution

        print(_metrics_dict(run_entity_resolution()))
        return
    if args.adapter == "statcan_denominators":
        from apps.jobs.analytics.denominators import run_statcan_denominators

        print(_metrics_dict(run_statcan_denominators()))
        return
    if args.adapter == "opportunity_analytics":
        from apps.jobs.analytics.opportunity import run_opportunity_analytics

        print(_metrics_dict(run_opportunity_analytics()))
        return
    if args.adapter == "peer_city_trends":
        from apps.jobs.analytics.trends import run_peer_city_trends

        print(_metrics_dict(run_peer_city_trends()))
        return
    if args.adapter == "people_graph":
        from apps.jobs.analytics.graph import run_graph_build

        print(_metrics_dict(run_graph_build()))
        return
    if args.adapter == "influence_scoring":
        from apps.jobs.analytics.influence import run_influence_scoring

        print(_metrics_dict(run_influence_scoring()))
        return
    if args.adapter == "m2":
        print(run_m2_sequence(limit=args.limit, people_csv=args.people_csv))
        return
    if args.adapter == "m3":
        print(run_m3_sequence())
        return

    metrics = run_adapter(adapter_for_name(args.adapter, args.limit))
    print(_metrics_dict(metrics))


def _metrics_dict(metrics: RunMetrics | Any) -> dict[str, Any]:
    return {
        "fetched": metrics.records_fetched,
        "persisted": metrics.records_persisted,
        "rejected": metrics.records_rejected,
        "errors": metrics.error_count,
    }


def run_m2_sequence(limit: int = 100, people_csv: Path | None = None) -> dict[str, Any]:
    results: dict[str, Any] = {}
    operator_adapters: list[Any] = [
        CityVancouverBusinessLicencesAdapter(limit=limit),
        ManualRecoverySeedAdapter(limit=limit),
        OsmOverpassAdapter(limit=limit),
    ]
    for adapter in operator_adapters:
        results[adapter.name] = _run_safely(lambda adapter=adapter: run_adapter(adapter))
    event_adapters: list[Any] = [
        RssFeedAdapter(limit=limit),
        BCGovHealthNewsAdapter(limit=limit),
        HealthCanadaRecallsAdapter(limit=limit),
    ]
    for adapter in event_adapters:
        results[adapter.name] = _run_safely(lambda adapter=adapter: run_event_adapter(adapter))
    results["orgbook_bc"] = _run_safely(lambda: run_orgbook_enrichment(limit=limit))
    results["manual_people_csv"] = _run_safely(
        lambda: import_people_csv(DatabaseRepository(), path=people_csv)
    )
    results["ai_enrichment"] = _run_safely(lambda: run_ai_enrichment(limit=limit))
    return results


def run_m3_sequence() -> dict[str, Any]:
    from apps.jobs.analytics.denominators import run_statcan_denominators
    from apps.jobs.analytics.entity_resolution import run_entity_resolution
    from apps.jobs.analytics.graph import run_graph_build
    from apps.jobs.analytics.influence import run_influence_scoring
    from apps.jobs.analytics.opportunity import run_opportunity_analytics
    from apps.jobs.analytics.trends import run_peer_city_trends

    results: dict[str, Any] = {}
    results["entity_resolution"] = _run_safely(run_entity_resolution)
    results["statcan_denominators"] = _run_safely(run_statcan_denominators)
    results["opportunity_analytics"] = _run_safely(run_opportunity_analytics)
    results["peer_city_trends"] = _run_safely(run_peer_city_trends)
    results["people_graph"] = _run_safely(run_graph_build)
    results["influence_scoring"] = _run_safely(run_influence_scoring)
    return results


def _run_safely(operation: Any) -> dict[str, Any]:
    try:
        result = operation()
        if isinstance(result, int):
            return {"enriched": result, "errors": 0}
        return _metrics_dict(result)
    except Exception as exc:
        return {"errors": 1, "error_message": str(exc)}


if __name__ == "__main__":
    main()
