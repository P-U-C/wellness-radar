from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from packages.schemas.canonical import SignalRecord, SourceEventRecord
from packages.shared.ids import stable_id
from packages.shared.normalizers import strip_html, truncate_text
from packages.shared.provenance import source_ref

WELLNESS_PERMIT_SEARCHES = (
    ("specificusecategory", "Fitness"),
    ("specificusecategory", "Wellness"),
    ("specificusecategory", "Health"),
    ("specificusecategory", "Massage"),
    ("specificusecategory", "Beauty"),
    ("projectdescription", "fitness"),
    ("projectdescription", "wellness"),
    ("projectdescription", "spa"),
    ("projectdescription", "massage"),
    ("projectdescription", "sauna"),
    ("projectdescription", "cold plunge"),
    ("projectdescription", "health enhancement"),
)


class CityVancouverBuildingPermitsAdapter:
    name = "city_vancouver_building_permits"
    family = "signal/permit"
    cadence = "weekly"
    trust_tier = "official"
    geo_aware = True
    base_url = "https://opendata.vancouver.ca/explore/dataset/issued-building-permits/"
    api_url = (
        "https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/"
        "issued-building-permits/records"
    )
    licence = "City of Vancouver Open Data Portal terms"

    def __init__(self, limit: int = 100, client: httpx.Client | None = None) -> None:
        self.limit = limit
        self.client = client or httpx.Client(timeout=30.0)

    def fetch(self) -> list[dict[str, Any]]:
        where = " OR ".join(
            f"search({field}, {term!r})" for field, term in WELLNESS_PERMIT_SEARCHES
        )
        response = self.client.get(
            self.api_url,
            params={"limit": self.limit, "where": where, "order_by": "-issuedate"},
        )
        response.raise_for_status()
        return list(response.json().get("results", []))

    def source_record_id(self, raw: dict[str, Any]) -> str:
        return str(raw.get("permitnumber") or "")

    def normalize(
        self, raw: dict[str, Any], raw_payload_id: str
    ) -> list[tuple[SourceEventRecord, SignalRecord]]:
        source_record_id = self.source_record_id(raw)
        if not source_record_id:
            return []
        if not _is_wellness_permit(raw):
            return []

        occurred_at = _parse_datetime(raw.get("issuedate") or raw.get("permitnumbercreateddate"))
        source_url = f"{self.base_url}?q={source_record_id}"
        refs = [
            source_ref(
                source_name=self.name,
                url=source_url,
                trust_tier=self.trust_tier,
                source_record_id=source_record_id,
                licence=self.licence,
                seen_at=occurred_at.isoformat().replace("+00:00", "Z"),
            )
        ]
        lat, lng = _point_for_raw(raw)
        address = _clean(raw.get("address"))
        use_categories = _string_list(raw.get("specificusecategory"))
        property_uses = _string_list(raw.get("propertyuse"))
        project_value = _float_or_none(raw.get("projectvalue"))
        description = truncate_text(strip_html(raw.get("projectdescription")), 480)
        category_label = ", ".join(use_categories) or "wellness-related use"
        title = f"Vancouver building permit issued for {category_label}"
        if address:
            title = f"{title}: {address}"

        payload = {
            "permit_number": source_record_id,
            "event_type": "building_permit_issued",
            "signal_type": "supply_pipeline_permit",
            "address": address,
            "municipality": "Vancouver",
            "province": "BC",
            "country": "CA",
            "project_value": project_value,
            "type_of_work": raw.get("typeofwork"),
            "permit_category": raw.get("permitcategory"),
            "property_use": property_uses,
            "specific_use_category": use_categories,
            "project_description": description,
            "applicant": raw.get("applicant"),
            "contractor": raw.get("buildingcontractor"),
            "local_area": raw.get("geolocalarea"),
            "bc_gate_text": _bc_gate_text(raw),
        }
        event = SourceEventRecord(
            id=stable_id("evt", self.name, source_record_id, "building_permit_issued"),
            source_name=self.name,
            raw_payload_id=raw_payload_id,
            source_record_id=source_record_id,
            event_type="building_permit_issued",
            entity_type=None,
            entity_id=None,
            title=title,
            occurred_at=occurred_at,
            trust_tier=self.trust_tier,
            lat=lat,
            lng=lng,
            source_refs=refs,
            confidence_score=0.86 if lat is not None and lng is not None else 0.72,
            payload=payload,
        )
        signal = SignalRecord(
            id=stable_id("sig", self.name, source_record_id, "supply_pipeline_permit"),
            type="supply_pipeline_permit",
            severity="info",
            title=title,
            summary=_summary_for_raw(raw, category_label, project_value),
            why_it_matters=(
                "Building permits are an official leading indicator for future wellness "
                "or fitness supply before an operator appears in licence data."
            ),
            source_name=self.name,
            source_url=source_url,
            trust_tier=self.trust_tier,
            occurred_at=occurred_at,
            lat=lat,
            lng=lng,
            related_operator_id=None,
            source_event_ids=[event.id],
            raw_payload_id=raw_payload_id,
            source_refs=refs,
            confidence_score=event.confidence_score,
        )
        return [(event, signal)]


def _is_wellness_permit(raw: dict[str, Any]) -> bool:
    text = _bc_gate_text(raw).lower()
    terms = {
        "fitness",
        "wellness",
        "health enhancement",
        "health care office",
        "massage",
        "spa",
        "sauna",
        "cold plunge",
        "beauty and wellness",
        "yoga",
        "pilates",
    }
    return any(term in text for term in terms)


def _summary_for_raw(raw: dict[str, Any], category_label: str, project_value: float | None) -> str:
    value_text = f" with project value ${project_value:,.0f}" if project_value else ""
    work = _clean(raw.get("typeofwork")) or "a building permit"
    address = _clean(raw.get("address"))
    address_text = f" at {address}" if address else ""
    return f"City of Vancouver issued {work} for {category_label}{address_text}{value_text}."


def _bc_gate_text(raw: dict[str, Any]) -> str:
    values = [
        raw.get("address"),
        "Vancouver BC",
        raw.get("geolocalarea"),
        raw.get("propertyuse"),
        raw.get("specificusecategory"),
        raw.get("projectdescription"),
    ]
    return " ".join(str(value) for value in values if value)


def _point_for_raw(raw: dict[str, Any]) -> tuple[float | None, float | None]:
    point_raw = raw.get("geo_point_2d")
    point: dict[str, Any] = point_raw if isinstance(point_raw, dict) else {}
    lat = _float_or_none(point.get("lat"))
    lng = _float_or_none(point.get("lon"))
    if lat is not None and lng is not None:
        return lat, lng
    geom_raw = raw.get("geom")
    geom = geom_raw if isinstance(geom_raw, dict) else {}
    geometry_raw = geom.get("geometry")
    geometry = geometry_raw if isinstance(geometry_raw, dict) else {}
    coordinates = geometry.get("coordinates")
    if isinstance(coordinates, list) and len(coordinates) >= 2:
        return _float_or_none(coordinates[1]), _float_or_none(coordinates[0])
    return None, None


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: Any) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _clean(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
