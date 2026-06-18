from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from packages.geo.bc_gate import BC_BBOX
from packages.schemas.canonical import CanonicalOperator
from packages.shared.ids import stable_id
from packages.shared.normalizers import compact_address, normalize_categories, normalize_name
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

    def __init__(self, limit: int = 200, client: httpx.Client | None = None) -> None:
        self.limit = limit
        self.client = client or httpx.Client(
            timeout=45.0,
            headers={"user-agent": "wellness-radar/0.1", "accept": "application/json,*/*"},
        )

    def fetch(self) -> list[dict[str, Any]]:
        min_lng, min_lat, max_lng, max_lat = BC_BBOX
        bbox = f"{min_lat},{min_lng},{max_lat},{max_lng}"
        query = f"""
        [out:json][timeout:30];
        (
          nwr["leisure"~"^(sauna|fitness_centre)$"]({bbox});
          nwr["amenity"="spa"]({bbox});
          nwr["shop"="massage"]({bbox});
          nwr["healthcare"~"^(physiotherapist|alternative|massage)$"]({bbox});
        );
        out center {self.limit};
        """
        response = self.client.post(self.base_url, data={"data": query})
        response.raise_for_status()
        payload = response.json()
        return list(payload.get("elements", []))[: self.limit]

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
