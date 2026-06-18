from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from psycopg.types.json import Jsonb

from apps.jobs.runner import DatabaseRepository, RunMetrics
from packages.shared.ids import stable_id


@dataclass(frozen=True)
class EntityMatch:
    entity_type: str
    survivor_id: str
    duplicate_id: str
    status: str
    confidence_score: float
    deterministic_rule: str
    provenance: dict[str, Any]
    source_refs: list[dict[str, Any]]


class EntityResolutionRepository(DatabaseRepository):
    def operator_candidates(self) -> list[dict[str, Any]]:
        return list(
            self.conn.execute(
                """
                SELECT
                  a.id AS a_id,
                  b.id AS b_id,
                  a.name AS a_name,
                  b.name AS b_name,
                  a.normalized_name AS a_normalized_name,
                  b.normalized_name AS b_normalized_name,
                  a.municipality AS a_municipality,
                  b.municipality AS b_municipality,
                  a.orgbook_id AS a_orgbook_id,
                  b.orgbook_id AS b_orgbook_id,
                  a.confidence_score AS a_confidence_score,
                  b.confidence_score AS b_confidence_score,
                  a.source_refs AS a_source_refs,
                  b.source_refs AS b_source_refs,
                  similarity(a.normalized_name, b.normalized_name) AS name_similarity
                FROM "operator" a
                JOIN "operator" b ON a.id < b.id
                WHERE (
                  a.normalized_name = b.normalized_name
                  OR similarity(a.normalized_name, b.normalized_name) >= 0.92
                  OR (
                    a.orgbook_id IS NOT NULL
                    AND b.orgbook_id IS NOT NULL
                    AND a.orgbook_id = b.orgbook_id
                  )
                )
                AND NOT EXISTS (
                  SELECT 1
                  FROM entity_resolution_match erm
                  WHERE erm.entity_type = 'operator'
                    AND erm.duplicate_id IN (a.id, b.id)
                    AND erm.status IN ('merged', 'candidate')
                )
                LIMIT 500
                """
            ).fetchall()
        )

    def organization_candidates(self) -> list[dict[str, Any]]:
        return list(
            self.conn.execute(
                """
                SELECT
                  a.id AS a_id,
                  b.id AS b_id,
                  a.name AS a_name,
                  b.name AS b_name,
                  a.normalized_name AS a_normalized_name,
                  b.normalized_name AS b_normalized_name,
                  a.orgbook_id AS a_orgbook_id,
                  b.orgbook_id AS b_orgbook_id,
                  a.registry_id AS a_registry_id,
                  b.registry_id AS b_registry_id,
                  a.confidence_score AS a_confidence_score,
                  b.confidence_score AS b_confidence_score,
                  a.source_refs AS a_source_refs,
                  b.source_refs AS b_source_refs,
                  similarity(a.normalized_name, b.normalized_name) AS name_similarity
                FROM organization a
                JOIN organization b ON a.id < b.id
                WHERE (
                  a.normalized_name = b.normalized_name
                  OR similarity(a.normalized_name, b.normalized_name) >= 0.94
                  OR (
                    a.orgbook_id IS NOT NULL
                    AND b.orgbook_id IS NOT NULL
                    AND a.orgbook_id = b.orgbook_id
                  )
                  OR (
                    a.registry_id IS NOT NULL
                    AND b.registry_id IS NOT NULL
                    AND a.registry_id = b.registry_id
                  )
                )
                AND NOT EXISTS (
                  SELECT 1
                  FROM entity_resolution_match erm
                  WHERE erm.entity_type = 'organization'
                    AND erm.duplicate_id IN (a.id, b.id)
                    AND erm.status IN ('merged', 'candidate')
                )
                LIMIT 500
                """
            ).fetchall()
        )

    def person_candidates(self) -> list[dict[str, Any]]:
        return list(
            self.conn.execute(
                """
                SELECT
                  a.id AS a_id,
                  b.id AS b_id,
                  a.name AS a_name,
                  b.name AS b_name,
                  a.normalized_name AS a_normalized_name,
                  b.normalized_name AS b_normalized_name,
                  a.affiliations AS a_affiliations,
                  b.affiliations AS b_affiliations,
                  a.confidence_score AS a_confidence_score,
                  b.confidence_score AS b_confidence_score,
                  a.source_refs AS a_source_refs,
                  b.source_refs AS b_source_refs,
                  similarity(a.normalized_name, b.normalized_name) AS name_similarity
                FROM person a
                JOIN person b ON a.id < b.id
                WHERE (
                  a.normalized_name = b.normalized_name
                  OR similarity(a.normalized_name, b.normalized_name) >= 0.96
                )
                AND NOT EXISTS (
                  SELECT 1
                  FROM entity_resolution_match erm
                  WHERE erm.entity_type = 'person'
                    AND erm.duplicate_id IN (a.id, b.id)
                    AND erm.status IN ('merged', 'candidate')
                )
                LIMIT 250
                """
            ).fetchall()
        )

    def upsert_match(self, match: EntityMatch) -> None:
        match_id = stable_id(
            "erm",
            match.entity_type,
            match.survivor_id,
            match.duplicate_id,
            match.deterministic_rule,
        )
        self.conn.execute(
            """
            INSERT INTO entity_resolution_match (
              id,
              entity_type,
              survivor_id,
              duplicate_id,
              status,
              confidence_score,
              deterministic_rule,
              provenance,
              source_refs
            )
            VALUES (
              %s, %s, %s, %s, %s::entity_match_status, %s, %s, %s, %s
            )
            ON CONFLICT (id) DO UPDATE SET
              status = EXCLUDED.status,
              confidence_score = EXCLUDED.confidence_score,
              deterministic_rule = EXCLUDED.deterministic_rule,
              provenance = EXCLUDED.provenance,
              source_refs = EXCLUDED.source_refs,
              updated_at = now()
            """,
            (
                match_id,
                match.entity_type,
                match.survivor_id,
                match.duplicate_id,
                match.status,
                match.confidence_score,
                match.deterministic_rule,
                Jsonb(match.provenance),
                Jsonb(match.source_refs),
            ),
        )
        if match.status == "merged":
            self.conn.execute(
                """
                INSERT INTO entity_alias (
                  entity_type,
                  alias_id,
                  canonical_id,
                  match_id,
                  active,
                  source_refs
                )
                VALUES (%s, %s, %s, %s, TRUE, %s)
                ON CONFLICT (entity_type, alias_id) DO UPDATE SET
                  canonical_id = EXCLUDED.canonical_id,
                  match_id = EXCLUDED.match_id,
                  active = TRUE,
                  source_refs = EXCLUDED.source_refs,
                  deactivated_at = NULL
                """,
                (
                    match.entity_type,
                    match.duplicate_id,
                    match.survivor_id,
                    match_id,
                    Jsonb(match.source_refs),
                ),
            )


def run_entity_resolution(
    repository: EntityResolutionRepository | None = None,
) -> RunMetrics:
    repo = repository or EntityResolutionRepository()
    metrics = RunMetrics()
    try:
        matches = [
            *[_operator_match(row) for row in repo.operator_candidates()],
            *[_organization_match(row) for row in repo.organization_candidates()],
            *[_person_match(row) for row in repo.person_candidates()],
        ]
        matches = _dedupe_active_duplicates(matches)
        metrics.records_fetched = len(matches)
        for match in matches:
            repo.upsert_match(match)
            metrics.records_persisted += 1
        return metrics
    finally:
        repo.close()


def _operator_match(row: dict[str, Any]) -> EntityMatch:
    rule, confidence = _operator_rule(row)
    survivor_id, duplicate_id = _survivor_duplicate(row)
    status = "merged" if confidence >= 0.95 else "candidate"
    return EntityMatch(
        entity_type="operator",
        survivor_id=survivor_id,
        duplicate_id=duplicate_id,
        status=status,
        confidence_score=confidence,
        deterministic_rule=rule,
        provenance=_match_provenance(row, rule),
        source_refs=_unique_refs([*row["a_source_refs"], *row["b_source_refs"]]),
    )


def _dedupe_active_duplicates(matches: Iterable[EntityMatch]) -> list[EntityMatch]:
    by_duplicate: dict[tuple[str, str], EntityMatch] = {}
    for match in matches:
        key = (match.entity_type, match.duplicate_id)
        existing = by_duplicate.get(key)
        if existing is None or match.confidence_score > existing.confidence_score:
            by_duplicate[key] = match
    return list(by_duplicate.values())


def _organization_match(row: dict[str, Any]) -> EntityMatch:
    rule, confidence = _organization_rule(row)
    survivor_id, duplicate_id = _survivor_duplicate(row)
    status = "merged" if confidence >= 0.95 else "candidate"
    return EntityMatch(
        entity_type="organization",
        survivor_id=survivor_id,
        duplicate_id=duplicate_id,
        status=status,
        confidence_score=confidence,
        deterministic_rule=rule,
        provenance=_match_provenance(row, rule),
        source_refs=_unique_refs([*row["a_source_refs"], *row["b_source_refs"]]),
    )


def _person_match(row: dict[str, Any]) -> EntityMatch:
    overlap = _affiliation_overlap(row["a_affiliations"], row["b_affiliations"])
    similarity = float(row["name_similarity"])
    confidence = 0.96 if row["a_normalized_name"] == row["b_normalized_name"] and overlap else 0.86
    if similarity >= 0.98 and overlap:
        confidence = max(confidence, 0.9)
    rule = "exact_public_name_and_affiliation" if overlap else "name_similarity_review"
    survivor_id, duplicate_id = _survivor_duplicate(row)
    return EntityMatch(
        entity_type="person",
        survivor_id=survivor_id,
        duplicate_id=duplicate_id,
        status="merged" if confidence >= 0.95 else "candidate",
        confidence_score=confidence,
        deterministic_rule=rule,
        provenance={**_match_provenance(row, rule), "public_affiliation_overlap": overlap},
        source_refs=_unique_refs([*row["a_source_refs"], *row["b_source_refs"]]),
    )


def _operator_rule(row: dict[str, Any]) -> tuple[str, float]:
    if row["a_orgbook_id"] and row["a_orgbook_id"] == row["b_orgbook_id"]:
        return "same_orgbook_id", 0.99
    same_municipality = _same_text(row["a_municipality"], row["b_municipality"])
    if row["a_normalized_name"] == row["b_normalized_name"] and same_municipality:
        return "exact_normalized_name_same_municipality", 0.97
    if float(row["name_similarity"]) >= 0.95 and same_municipality:
        return "pg_trgm_name_similarity_same_municipality", 0.9
    return "pg_trgm_name_similarity_review", 0.84


def _organization_rule(row: dict[str, Any]) -> tuple[str, float]:
    if row["a_orgbook_id"] and row["a_orgbook_id"] == row["b_orgbook_id"]:
        return "same_orgbook_id", 0.99
    if row["a_registry_id"] and row["a_registry_id"] == row["b_registry_id"]:
        return "same_registry_id", 0.98
    if row["a_normalized_name"] == row["b_normalized_name"]:
        return "exact_normalized_legal_name", 0.96
    if float(row["name_similarity"]) >= 0.96:
        return "pg_trgm_legal_name_similarity", 0.88
    return "pg_trgm_legal_name_review", 0.82


def _survivor_duplicate(row: dict[str, Any]) -> tuple[str, str]:
    a_conf = float(row["a_confidence_score"])
    b_conf = float(row["b_confidence_score"])
    if a_conf > b_conf:
        return str(row["a_id"]), str(row["b_id"])
    if b_conf > a_conf:
        return str(row["b_id"]), str(row["a_id"])
    return min(str(row["a_id"]), str(row["b_id"])), max(str(row["a_id"]), str(row["b_id"]))


def _match_provenance(row: dict[str, Any], rule: str) -> dict[str, Any]:
    return {
        "rule": rule,
        "left": {
            "id": row["a_id"],
            "name": row["a_name"],
            "normalized_name": row["a_normalized_name"],
            "confidence_score": float(row["a_confidence_score"]),
        },
        "right": {
            "id": row["b_id"],
            "name": row["b_name"],
            "normalized_name": row["b_normalized_name"],
            "confidence_score": float(row["b_confidence_score"]),
        },
        "pg_trgm_similarity": round(float(row["name_similarity"]), 4),
        "reversible": True,
        "merge_mode": "logical_alias_only",
    }


def _same_text(left: object, right: object) -> bool:
    return bool(left and right and str(left).strip().lower() == str(right).strip().lower())


def _affiliation_overlap(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> bool:
    left_names = {
        str(item.get("organization_name") or "").strip().lower()
        for item in left
        if item.get("organization_name")
    }
    right_names = {
        str(item.get("organization_name") or "").strip().lower()
        for item in right
        if item.get("organization_name")
    }
    return bool(left_names.intersection(right_names))


def _unique_refs(refs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for ref in refs:
        key = "|".join(str(ref.get(field)) for field in ("source_name", "url", "source_record_id"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(ref)
    return unique
