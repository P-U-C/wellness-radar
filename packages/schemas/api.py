from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PageMeta(BaseModel):
    count: int
    bbox: list[float] | None = None


class OperatorItem(BaseModel):
    id: str
    name: str
    categories: list[str]
    status: str
    address: str | None
    municipality: str | None
    neighborhood: str | None
    neighborhood_assignment_method: str | None = None
    neighborhood_assignment_source: str | None = None
    neighborhood_assignment_confidence: float | None = None
    lat: float
    lng: float
    confidence_score: float
    source_refs: list[dict[str, Any]]


class OperatorsResponse(BaseModel):
    items: list[OperatorItem]
    meta: PageMeta


class SignalItem(BaseModel):
    id: str
    type: str
    severity: str
    title: str
    summary: str | None
    why_it_matters: str | None
    source_name: str
    source_url: str | None
    trust_tier: str
    occurred_at: str
    lat: float | None
    lng: float | None
    related_operator_id: str | None
    confidence_score: float
    source_refs: list[dict[str, Any]]


class SignalsResponse(BaseModel):
    items: list[SignalItem]
    meta: PageMeta


class BundleSummaryItem(BaseModel):
    id: str
    label: str
    slug: str
    bundle_score: float
    score: float
    components: dict[str, Any]
    geography: dict[str, Any]
    member_count: int
    supporting_signals: list[dict[str, Any]]
    source_refs: list[dict[str, Any]]
    confidence_score: float
    generated_at: str
    freshness_at: str
    freshness_age_hours: float | None


class BundleMemberItem(BaseModel):
    id: str
    name: str
    categories: list[str]
    status: str
    address: str | None
    municipality: str | None
    neighborhood: str | None
    lat: float
    lng: float
    phone: str | None = None
    website: str | None = None
    social_links: dict[str, Any]
    contacts: list[dict[str, Any]]
    organization_id: str | None = None
    orgbook_id: str | None = None
    match_reasons: dict[str, Any]
    membership_confidence_score: float
    confidence_score: float
    source_refs: list[dict[str, Any]]
    freshness_at: str | None
    freshness_age_hours: float | None


class BundlePersonItem(BaseModel):
    id: str
    name: str
    roles: list[str]
    primary_role: str | None
    primary_affiliation: str | None
    rank: int
    influence_score: float | None
    why_appears: str
    public_profiles: dict[str, Any]
    confidence_score: float
    source_refs: list[dict[str, Any]]
    freshness_at: str | None
    freshness_age_hours: float | None


class BundleWorldwideMatch(BaseModel):
    direction: str
    value: float
    verdict: str
    source_status: str
    confidence_score: float | None = None
    window_days: int | None = None
    methodology_version: str | None = None
    components: dict[str, Any] = Field(default_factory=dict)
    source_errors: list[str] = Field(default_factory=list)
    source_refs: list[dict[str, Any]]


class BundleFirstMoverCityItem(BaseModel):
    city: str
    count: int
    density: float
    ratio_vs_vancouver: float
    source_status: str
    confidence_score: float
    source_error: str | None = None
    source_refs: list[dict[str, Any]]


class BundlesResponse(BaseModel):
    items: list[BundleSummaryItem]
    meta: dict[str, Any]


class BundleDetailResponse(BundleSummaryItem):
    members: list[BundleMemberItem]
    top_people: list[BundlePersonItem]
    worldwide_match: BundleWorldwideMatch | None = None
    first_mover_cities: list[BundleFirstMoverCityItem] = Field(default_factory=list)
