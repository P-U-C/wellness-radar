from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from psycopg.types.json import Jsonb

from apps.jobs.runner import DatabaseRepository, RunMetrics

INFLUENCE_METHOD_VERSION = "m3_influence_v1"
INFLUENCE_FORMULA = (
    "0.25 institutional_authority + 0.20 network_centrality + "
    "0.15 research_or_clinical_leadership + 0.15 media_velocity + "
    "0.10 capital_power + 0.10 event_convening + 0.05 public_reach, "
    "then multiplied by locality_multiplier, recency_decay, and source_confidence."
)


@dataclass(frozen=True)
class InfluenceComponents:
    institutional_authority: float
    network_centrality: float
    research_or_clinical_leadership: float
    media_velocity: float
    capital_power: float
    event_convening: float
    public_reach: float
    locality_multiplier: float
    recency_decay: float
    source_confidence: float

    def raw_weighted(self) -> float:
        return (
            0.25 * self.institutional_authority
            + 0.20 * self.network_centrality
            + 0.15 * self.research_or_clinical_leadership
            + 0.15 * self.media_velocity
            + 0.10 * self.capital_power
            + 0.10 * self.event_convening
            + 0.05 * self.public_reach
        )

    def final_score(self) -> float:
        return round(
            self.raw_weighted()
            * self.locality_multiplier
            * self.recency_decay
            * self.source_confidence,
            4,
        )

    def as_dict(self) -> dict[str, float | str]:
        return {
            "institutional_authority": self.institutional_authority,
            "network_centrality": self.network_centrality,
            "research_or_clinical_leadership": self.research_or_clinical_leadership,
            "media_velocity": self.media_velocity,
            "capital_power": self.capital_power,
            "event_convening": self.event_convening,
            "public_reach": self.public_reach,
            "locality_multiplier": self.locality_multiplier,
            "recency_decay": self.recency_decay,
            "source_confidence": self.source_confidence,
            "formula": INFLUENCE_FORMULA,
        }


class InfluenceRepository(DatabaseRepository):
    def people_for_scoring(self) -> list[dict[str, Any]]:
        return list(
            self.conn.execute(
                """
                SELECT
                  p.id,
                  p.name,
                  p.roles,
                  p.affiliations,
                  p.public_profiles,
                  p.confidence_score,
                  p.source_refs,
                  p.last_seen_at,
                  COALESCE(n.centrality, 0) AS network_centrality
                FROM person p
                LEFT JOIN entity_graph_node n
                  ON n.node_type = 'person'
                 AND n.entity_id = p.id
                WHERE jsonb_array_length(p.source_refs) > 0
                """
            ).fetchall()
        )

    def media_mentions(self, person_id: str) -> tuple[int, list[dict[str, Any]], float]:
        rows = self.conn.execute(
            """
            SELECT source_refs, confidence_score
            FROM signal
            WHERE %s = ANY(related_person_ids)
              AND occurred_at >= now() - interval '180 days'
            """,
            (person_id,),
        ).fetchall()
        refs = _unique_refs(ref for row in rows for ref in row["source_refs"])
        confidence = _average([float(row["confidence_score"]) for row in rows], default=0.0)
        return len(rows), refs, confidence

    def event_mentions(self, person_name: str) -> tuple[int, list[dict[str, Any]]]:
        rows = self.conn.execute(
            """
            SELECT source_refs
            FROM event
            WHERE lower(title) LIKE %s
               OR EXISTS (
                 SELECT 1
                 FROM unnest(topics) topic
                 WHERE lower(topic) LIKE %s
               )
            """,
            (f"%{person_name.lower()}%", f"%{person_name.lower()}%"),
        ).fetchall()
        refs = _unique_refs(ref for row in rows for ref in row["source_refs"])
        return len(rows), refs

    def upsert_influence(
        self,
        person: dict[str, Any],
        components: InfluenceComponents,
        explanation: str,
        source_refs: list[dict[str, Any]],
    ) -> None:
        score = components.final_score()
        self.conn.execute(
            """
            INSERT INTO person_influence_component (
              person_id,
              institutional_authority,
              network_centrality,
              research_or_clinical_leadership,
              media_velocity,
              capital_power,
              event_convening,
              public_reach,
              locality_multiplier,
              recency_decay,
              source_confidence,
              influence_score,
              component_breakdown,
              explanation,
              methodology_version,
              source_refs,
              confidence_score
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (person_id) DO UPDATE SET
              institutional_authority = EXCLUDED.institutional_authority,
              network_centrality = EXCLUDED.network_centrality,
              research_or_clinical_leadership = EXCLUDED.research_or_clinical_leadership,
              media_velocity = EXCLUDED.media_velocity,
              capital_power = EXCLUDED.capital_power,
              event_convening = EXCLUDED.event_convening,
              public_reach = EXCLUDED.public_reach,
              locality_multiplier = EXCLUDED.locality_multiplier,
              recency_decay = EXCLUDED.recency_decay,
              source_confidence = EXCLUDED.source_confidence,
              influence_score = EXCLUDED.influence_score,
              component_breakdown = EXCLUDED.component_breakdown,
              explanation = EXCLUDED.explanation,
              methodology_version = EXCLUDED.methodology_version,
              source_refs = EXCLUDED.source_refs,
              confidence_score = EXCLUDED.confidence_score,
              calculated_at = now()
            """,
            (
                person["id"],
                components.institutional_authority,
                components.network_centrality,
                components.research_or_clinical_leadership,
                components.media_velocity,
                components.capital_power,
                components.event_convening,
                components.public_reach,
                components.locality_multiplier,
                components.recency_decay,
                components.source_confidence,
                score,
                Jsonb(components.as_dict()),
                explanation,
                INFLUENCE_METHOD_VERSION,
                Jsonb(source_refs),
                components.source_confidence,
            ),
        )
        self.conn.execute(
            """
            UPDATE person
            SET influence_score = %s,
                locality_score = %s,
                confidence_score = GREATEST(confidence_score, %s),
                last_seen_at = now()
            WHERE id = %s
            """,
            (
                score,
                components.locality_multiplier,
                components.source_confidence,
                person["id"],
            ),
        )


def run_influence_scoring(
    repository: InfluenceRepository | None = None,
) -> RunMetrics:
    repo = repository or InfluenceRepository()
    metrics = RunMetrics()
    try:
        people = repo.people_for_scoring()
        metrics.records_fetched = len(people)
        for person in people:
            media_count, media_refs, media_confidence = repo.media_mentions(str(person["id"]))
            event_count, event_refs = repo.event_mentions(str(person["name"]))
            components = components_for_person(
                person=person,
                media_count=media_count,
                media_confidence=media_confidence,
                event_count=event_count,
            )
            source_refs = _unique_refs([*person["source_refs"], *media_refs, *event_refs])
            if not source_refs:
                continue
            explanation = why_person_appears(person, components, media_count, event_count)
            repo.upsert_influence(person, components, explanation, source_refs)
            metrics.records_persisted += 1
        return metrics
    finally:
        repo.close()


def components_for_person(
    *,
    person: dict[str, Any],
    media_count: int,
    media_confidence: float,
    event_count: int,
) -> InfluenceComponents:
    roles = " ".join(person["roles"]).lower()
    affiliations = " ".join(
        str(item.get("organization_name") or "") for item in person["affiliations"]
    ).lower()
    institutional_authority = _institutional_authority(roles, affiliations)
    network_centrality = _clamp(float(person["network_centrality"]))
    research_or_clinical = _research_or_clinical(str(person["name"]), roles)
    media_velocity = _clamp(media_count / 5)
    if media_count and media_confidence:
        media_velocity = round(media_velocity * max(media_confidence, 0.5), 4)
    capital_power = _capital_power(roles)
    event_convening = _clamp(event_count / 4)
    public_reach = _public_reach(person["public_profiles"], roles, affiliations)
    locality_multiplier = _locality_multiplier(affiliations)
    recency_decay = _recency_decay(person["last_seen_at"])
    source_confidence = _clamp(float(person["confidence_score"]))
    return InfluenceComponents(
        institutional_authority=round(institutional_authority, 4),
        network_centrality=round(network_centrality, 4),
        research_or_clinical_leadership=round(research_or_clinical, 4),
        media_velocity=round(media_velocity, 4),
        capital_power=round(capital_power, 4),
        event_convening=round(event_convening, 4),
        public_reach=round(public_reach, 4),
        locality_multiplier=round(locality_multiplier, 4),
        recency_decay=round(recency_decay, 4),
        source_confidence=round(source_confidence, 4),
    )


def why_person_appears(
    person: dict[str, Any],
    components: InfluenceComponents,
    media_count: int,
    event_count: int,
) -> str:
    role = person["roles"][0] if person["roles"] else "public professional"
    affiliation = ""
    if person["affiliations"]:
        affiliation = str(person["affiliations"][0].get("organization_name") or "")
    reasons = [
        f"Public professional role: {role}",
        f"Affiliation: {affiliation}" if affiliation else "Affiliation is source-backed",
        f"Network centrality component: {components.network_centrality:.2f}",
    ]
    if media_count:
        reasons.append(f"{media_count} source-backed signal mention(s) in 180d")
    if event_count:
        reasons.append(f"{event_count} public event/convening match(es)")
    return "; ".join(reasons)


def _institutional_authority(roles: str, affiliations: str) -> float:
    if "minister" in roles or "provincial health officer" in roles:
        return 0.95
    if "government" in affiliations or "health authority" in affiliations:
        return 0.82
    if "advocate" in roles or "attorney general" in roles:
        return 0.74
    if "operator" in roles:
        return 0.42
    return 0.3


def _research_or_clinical(name: str, roles: str) -> float:
    lowered = f"{name} {roles}".lower()
    if "dr." in lowered or "doctor" in lowered or "physician" in lowered:
        return 0.85
    if "health officer" in lowered or "clinical" in lowered or "research" in lowered:
        return 0.78
    if "practitioner" in lowered or "therapist" in lowered:
        return 0.55
    return 0.15


def _capital_power(roles: str) -> float:
    if "investor" in roles or "founder" in roles:
        return 0.7
    if "minister" in roles or "attorney general" in roles:
        return 0.55
    if "operator" in roles:
        return 0.35
    return 0.1


def _public_reach(public_profiles: dict[str, Any], roles: str, affiliations: str) -> float:
    score = 0.25 if public_profiles.get("primary") else 0.1
    if "government" in affiliations:
        score += 0.35
    if "minister" in roles or "health officer" in roles:
        score += 0.25
    return _clamp(score)


def _locality_multiplier(affiliations: str) -> float:
    if any(token in affiliations for token in ("british columbia", "b.c.", "bc", "vancouver")):
        return 1.12
    return 1.0


def _recency_decay(last_seen_at: datetime) -> float:
    now = datetime.now(timezone.utc)
    if last_seen_at.tzinfo is None:
        last_seen_at = last_seen_at.replace(tzinfo=timezone.utc)
    age_days = max((now - last_seen_at).days, 0)
    return _clamp(math.exp(-age_days / 730))


def _average(values: list[float], *, default: float) -> float:
    if not values:
        return default
    return sum(values) / len(values)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


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
