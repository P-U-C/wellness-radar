from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

import httpx

from packages.schemas.canonical import CanonicalOrganization
from packages.shared.ids import stable_id
from packages.shared.normalizers import normalize_legal_name, normalize_name
from packages.shared.provenance import source_ref


@dataclass(frozen=True)
class OrgBookMatch:
    orgbook_id: str | None
    registry_id: str | None
    legal_name: str
    organization_type: str | None
    status: str
    confidence: float
    source_url: str


class OrgBookBCEnrichmentAdapter:
    name = "orgbook_bc"
    family = "organization"
    cadence = "daily/weekly"
    trust_tier = "official"
    geo_aware = False
    base_url = "https://orgbook.gov.bc.ca"
    search_url = "https://orgbook.gov.bc.ca/api/v4/search/topic"
    licence = "BC Gov public registry access terms"

    def __init__(self, limit: int = 100, client: httpx.Client | None = None) -> None:
        self.limit = limit
        self.client = client or httpx.Client(timeout=30.0)

    def fetch_for_operator(self, operator_name: str) -> dict[str, Any]:
        response = self.client.get(
            self.search_url,
            params={"q": operator_name, "page_size": 10},
        )
        response.raise_for_status()
        return response.json()

    def source_record_id(self, operator_id: str) -> str:
        return operator_id

    def match(self, operator_name: str, payload: dict[str, Any]) -> OrgBookMatch:
        target = normalize_legal_name(operator_name)
        best: OrgBookMatch | None = None
        for result in payload.get("results", []):
            legal_names = [
                str(name.get("text"))
                for name in result.get("names", [])
                if name.get("type") == "entity_name" and name.get("text")
            ]
            for legal_name in legal_names:
                candidate = normalize_legal_name(legal_name)
                confidence = _match_confidence(target, candidate)
                if confidence < 0.88:
                    continue
                orgbook_id = str(result.get("id") or "")
                match = OrgBookMatch(
                    orgbook_id=orgbook_id,
                    registry_id=str(result.get("source_id") or "") or None,
                    legal_name=legal_name,
                    organization_type=_attribute_value(result, "entity_type"),
                    status="matched",
                    confidence=confidence,
                    source_url=f"{self.base_url}/entity/{orgbook_id}",
                )
                if best is None or match.confidence > best.confidence:
                    best = match

        if best is not None:
            return best
        return OrgBookMatch(
            orgbook_id=None,
            registry_id=None,
            legal_name=operator_name,
            organization_type=None,
            status="unmatched",
            confidence=0.0,
            source_url=f"{self.base_url}/search?q={operator_name}",
        )

    def organization_for_operator(
        self,
        *,
        operator_id: str,
        operator_name: str,
        operator_website: str | None,
        match: OrgBookMatch,
    ) -> CanonicalOrganization:
        source_record_id = match.orgbook_id or operator_id
        refs = [
            source_ref(
                source_name=self.name,
                url=match.source_url,
                trust_tier=self.trust_tier,
                source_record_id=source_record_id,
                licence=self.licence,
            )
        ]
        org_id = stable_id("org", match.orgbook_id or normalize_name(operator_name))
        return CanonicalOrganization(
            id=org_id,
            name=match.legal_name,
            normalized_name=normalize_name(match.legal_name),
            registry_id=match.registry_id,
            orgbook_id=match.orgbook_id,
            orgbook_match_status=match.status,
            orgbook_match_confidence=match.confidence,
            organization_type=match.organization_type,
            website=operator_website,
            social_links={},
            source_refs=refs,
            confidence_score=0.88 if match.orgbook_id else 0.45,
        )


def _match_confidence(target: str, candidate: str) -> float:
    if not target or not candidate:
        return 0.0
    if target == candidate:
        return 0.99
    if target in candidate or candidate in target:
        return 0.92
    return SequenceMatcher(None, target, candidate).ratio()


def _attribute_value(result: dict[str, Any], attribute_type: str) -> str | None:
    for attribute in result.get("attributes", []):
        if attribute.get("type") == attribute_type and attribute.get("value"):
            return str(attribute["value"])
    return None
