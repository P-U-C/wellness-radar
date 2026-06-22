from __future__ import annotations

from typing import Any

from pydantic import BaseModel


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
