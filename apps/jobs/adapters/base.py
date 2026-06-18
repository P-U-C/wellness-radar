from __future__ import annotations

from typing import Protocol

from packages.schemas.canonical import CanonicalOperator


class SourceAdapter(Protocol):
    name: str
    family: str
    cadence: str
    trust_tier: str
    geo_aware: bool

    def fetch(self) -> list[dict]:
        ...

    def normalize(self, raw: dict, raw_payload_id: str) -> list[CanonicalOperator]:
        ...

    def source_record_id(self, raw: dict) -> str:
        ...
