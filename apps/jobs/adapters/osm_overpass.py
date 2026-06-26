from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from packages.geo.bc_gate import BC_BBOX
from packages.schemas.canonical import CanonicalOperator
from packages.shared.contacts import build_contact_method
from packages.shared.ids import stable_id
from packages.shared.normalizers import (
    compact_address,
    infer_service_model,
    normalize_categories,
    normalize_name,
)
from packages.shared.provenance import source_ref


class OsmOverpassAdapter:
    name = "osm_overpass"
    family = "directory"
    cadence = "weekly"
    trust_tier = "community"
    geo_aware = True
    dedupe_existing = True
    base_url = "https://overpass-api.de/api/interpreter"
    licence = "Open Database License"

    def __init__(self, limit: int = 2000, client: httpx.Client | None = None) -> None:
        self.limit = limit
        self.client = client or httpx.Client(
            timeout=90.0,
            headers={"user-agent": "wellness-radar/0.1", "accept": "application/json,*/*"},
        )

    def fetch(self) -> list[dict[str, Any]]:
        min_lng, min_lat, max_lng, max_lat = BC_BBOX
        bbox = f"{min_lat},{min_lng},{max_lat},{max_lng}"
        elements_by_id: dict[str, dict[str, Any]] = {}
        for selector_group in _OVERPASS_SELECTOR_GROUPS:
            query = _query_for_selectors(selector_group, bbox=bbox, limit=self.limit)
            response = self.client.post(self.base_url, data={"data": query})
            response.raise_for_status()
            payload = response.json()
            for element in payload.get("elements", []):
                if not isinstance(element, dict):
                    continue
                elements_by_id[self.source_record_id(element)] = element
                if len(elements_by_id) >= self.limit:
                    return list(elements_by_id.values())[: self.limit]
        return list(elements_by_id.values())[: self.limit]

    def source_record_id(self, raw: dict[str, Any]) -> str:
        return f"{raw.get('type', 'unknown')}/{raw.get('id', '')}"

    def normalize(self, raw: dict[str, Any], raw_payload_id: str) -> list[CanonicalOperator]:
        tags = raw.get("tags") or {}
        name = str(tags.get("name") or "").strip()
        if not name:
            return []

        categories = normalize_categories(
            name,
            tags.get("leisure"),
            tags.get("amenity"),
            tags.get("shop"),
            tags.get("healthcare"),
            tags.get("sport"),
            tags.get("massage"),
        )
        if not categories:
            return []
        is_mobile, service_area = infer_service_model(
            name,
            tags.get("description"),
            tags.get("service"),
            tags.get("service_area"),
            tags.get("delivery"),
            tags.get("healthcare"),
            tags.get("massage"),
        )

        source_record_id = self.source_record_id(raw)
        lat = _float_or_none(raw.get("lat") or (raw.get("center") or {}).get("lat"))
        lng = _float_or_none(raw.get("lon") or (raw.get("center") or {}).get("lon"))
        city = tags.get("addr:city") or _municipality_from_text(tags.get("addr:street"))
        province = tags.get("addr:province") or "BC"
        address = compact_address(
            compact_address(
                tags.get("addr:unit"),
                tags.get("addr:housenumber"),
                tags.get("addr:street"),
            ),
            city,
            province,
            tags.get("addr:postcode"),
        )
        source_url = _osm_url(raw)
        seen_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        refs = [
            source_ref(
                source_name=self.name,
                url=source_url,
                trust_tier=self.trust_tier,
                source_record_id=source_record_id,
                licence=self.licence,
                seen_at=seen_at,
            )
        ]
        confidence = 0.76 if lat is not None and lng is not None else 0.52
        phone = _first_tag(tags, "contact:phone", "phone")
        website = _first_tag(tags, "contact:website", "website")
        email = _first_tag(tags, "contact:email", "email")
        social_links: dict[str, str] = {}
        contacts: list[dict[str, Any]] = []
        ref = refs[0]
        for contact_type, value, platform in [
            ("phone", phone, None),
            ("website", website, None),
            ("email", email, None),
            ("social", _first_tag(tags, "contact:instagram", "instagram"), "instagram"),
            ("social", _first_tag(tags, "contact:facebook", "facebook"), "facebook"),
        ]:
            contact = build_contact_method(
                contact_type=contact_type,
                value=value,
                platform=platform,
                source_ref=ref,
                confidence=confidence,
            )
            if contact is None:
                continue
            contacts.append(contact)
            if contact_type == "social" and platform:
                social_links[platform] = str(contact["value"])
        normalized_website = next(
            (str(contact["value"]) for contact in contacts if contact["type"] == "website"),
            None,
        )
        normalized_phone = next(
            (str(contact["value"]) for contact in contacts if contact["type"] == "phone"),
            None,
        )

        return [
            CanonicalOperator(
                id=stable_id("op", self.name, source_record_id),
                source_name=self.name,
                source_record_id=source_record_id,
                raw_payload_id=raw_payload_id,
                name=name,
                normalized_name=normalize_name(name),
                categories=categories,
                status="open",
                address=address,
                municipality=city,
                province=province,
                country="CA",
                neighborhood=None,
                lat=lat,
                lng=lng,
                licence_ref=source_record_id,
                source_url=source_url,
                source_refs=refs,
                confidence_score=confidence,
                occurred_at=datetime.now(timezone.utc),
                is_mobile=is_mobile,
                service_area=service_area,
                phone=normalized_phone,
                website=normalized_website,
                social_links=social_links,
                contacts=contacts,
                payload={
                    "tags": tags,
                    "event_type": "poi_observed",
                    "signal_type": "operator_observed",
                    "signal_title": f"OSM wellness POI observed: {name}",
                    "signal_summary": f"{name} appears in OpenStreetMap wellness POI data.",
                    "trust_tier": self.trust_tier,
                },
            )
        ]


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _osm_url(raw: dict[str, Any]) -> str:
    osm_type = str(raw.get("type") or "node")
    osm_id = str(raw.get("id") or "")
    if osm_type == "way":
        return f"https://www.openstreetmap.org/way/{osm_id}"
    if osm_type == "relation":
        return f"https://www.openstreetmap.org/relation/{osm_id}"
    return f"https://www.openstreetmap.org/node/{osm_id}"


def _municipality_from_text(value: Any) -> str | None:
    text = str(value or "").lower()
    if "burnaby" in text:
        return "Burnaby"
    if "surrey" in text:
        return "Surrey"
    if "richmond" in text:
        return "Richmond"
    return None


def _first_tag(tags: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = tags.get(key)
        if value is not None and str(value).strip():
            return value
    return None


_OVERPASS_SELECTOR_GROUPS: tuple[tuple[str, ...], ...] = (
    (
        'nwr["sport"]',
    ),
    (
        'nwr["leisure"~"^(sauna|fitness_centre|fitness_station|sports_centre|sports_hall|pitch|track|swimming_pool|ice_rink|dance|stadium)$"]',
        'nwr["amenity"~"^(gym|spa)$"]',
        'nwr["shop"="massage"]',
        'nwr["healthcare"~"^(physiotherapist|alternative|massage)$"]',
    ),
    (
        'nwr["sauna"]',
        'nwr["bath:type"~"sauna|steam|thermal|hot_spring"]',
        'nwr["massage"]',
        'nwr["spa"]',
    ),
)


def _query_for_selectors(selectors: tuple[str, ...], *, bbox: str, limit: int) -> str:
    lines = "\n".join(f"          {selector}({bbox});" for selector in selectors)
    return f"""
        [out:json][timeout:90];
        (
{lines}
        );
        out center {limit};
        """
