from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from packages.schemas.canonical import CanonicalPerson
from packages.shared.ids import stable_id
from packages.shared.normalizers import normalize_name
from packages.shared.provenance import source_ref

DEFAULT_PEOPLE_PATH = Path(__file__).resolve().parents[3] / "db" / "seeds" / "manual_people.csv"


class PeopleRepository(Protocol):
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

    def upsert_person(self, person: CanonicalPerson) -> None:
        ...

    def rollback(self) -> None:
        ...

    def close(self) -> None:
        ...


@dataclass
class PeopleImportMetrics:
    records_fetched: int = 0
    records_persisted: int = 0
    records_rejected: int = 0
    error_count: int = 0
    error_message: str | None = None


def import_people_csv(
    repository: PeopleRepository,
    path: Path | None = None,
    *,
    source_name: str = "manual_people_csv",
) -> PeopleImportMetrics:
    metrics = PeopleImportMetrics()
    run_id = 0
    try:
        repository.ensure_source_rights(source_name)
        run_id = repository.create_source_run(source_name)
        rows = _read_rows(path or DEFAULT_PEOPLE_PATH)
        metrics.records_fetched = len(rows)
        for raw in rows:
            source_record_id = str(raw.get("source_record_id") or normalize_name(raw["name"]))
            raw_payload_id = repository.upsert_raw_payload(source_name, source_record_id, raw)
            person = _person_from_row(raw, raw_payload_id)
            repository.upsert_person(person)
            metrics.records_persisted += 1
        repository.complete_source_run(
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
            repository.rollback()
            repository.complete_source_run(
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
        repository.close()


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _person_from_row(raw: dict[str, str], raw_payload_id: str) -> CanonicalPerson:
    source_name = raw.get("source_name") or "manual_people_csv"
    source_record_id = raw.get("source_record_id") or normalize_name(raw["name"])
    roles = [role.strip() for role in raw.get("roles", "").split("|") if role.strip()]
    source_url = raw.get("source_url") or None
    refs = [
        source_ref(
            source_name=source_name,
            url=source_url,
            trust_tier="informal",
            source_record_id=source_record_id,
            licence="source-specific public professional page",
        )
    ]
    affiliation = {
        "organization_name": raw.get("affiliation_name"),
        "role": raw.get("affiliation_role"),
        "source_record_id": source_record_id,
    }
    return CanonicalPerson(
        id=stable_id("person", normalize_name(raw["name"])),
        name=raw["name"],
        normalized_name=normalize_name(raw["name"]),
        roles=roles,
        affiliations=[affiliation],
        public_profiles={"primary": source_url, "raw_payload_id": raw_payload_id},
        confidence_score=float(raw.get("confidence_score") or 0.5),
        source_refs=refs,
    )
