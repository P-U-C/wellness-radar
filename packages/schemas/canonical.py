from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

CATEGORIES = [
    "recovery_contrast_therapy",
    "fitness_movement",
    "mind_meditation",
    "spa_thermal",
    "nutrition_longevity",
    "allied_health",
    "womens_health",
    "preventive_diagnostic",
    "mental_health",
    "community_social_wellness",
    "wellness_retail_product",
]

TRUST_TIERS = [
    "official",
    "reputable_press",
    "commercial_api",
    "community",
    "informal",
    "ai_inferred",
]

OPERATOR_STATUSES = ["open", "new", "planned", "closed", "rumored", "unknown"]


@dataclass(frozen=True)
class SourceRef:
    source_name: str
    url: str | None
    trust_tier: str
    seen_at: str
    source_record_id: str | None = None
    licence: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_name": self.source_name,
            "url": self.url,
            "trust_tier": self.trust_tier,
            "seen_at": self.seen_at,
            "source_record_id": self.source_record_id,
            "licence": self.licence,
        }


@dataclass
class CanonicalOperator:
    id: str
    source_name: str
    source_record_id: str
    raw_payload_id: str
    name: str
    normalized_name: str
    categories: list[str]
    status: str
    address: str | None
    municipality: str | None
    province: str | None
    country: str | None
    neighborhood: str | None
    lat: float | None
    lng: float | None
    licence_ref: str | None
    source_url: str | None
    source_refs: list[dict[str, Any]]
    confidence_score: float
    occurred_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceEventRecord:
    id: str
    source_name: str
    raw_payload_id: str
    source_record_id: str
    event_type: str
    entity_type: str
    entity_id: str
    title: str
    occurred_at: datetime
    trust_tier: str
    lat: float | None
    lng: float | None
    source_refs: list[dict[str, Any]]
    confidence_score: float
    payload: dict[str, Any]


@dataclass
class SignalRecord:
    id: str
    type: str
    severity: str
    title: str
    summary: str
    why_it_matters: str
    source_name: str
    source_url: str | None
    trust_tier: str
    occurred_at: datetime
    lat: float | None
    lng: float | None
    related_operator_id: str
    source_event_ids: list[str]
    raw_payload_id: str
    source_refs: list[dict[str, Any]]
    confidence_score: float
