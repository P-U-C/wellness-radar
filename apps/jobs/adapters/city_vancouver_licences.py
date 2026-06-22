from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from packages.schemas.canonical import CanonicalOperator
from packages.shared.contacts import build_contact_method
from packages.shared.dedupe import choose_best_name
from packages.shared.ids import stable_id
from packages.shared.normalizers import (
    compact_address,
    normalize_categories,
    normalize_name,
    normalize_status,
)
from packages.shared.provenance import source_ref


class CityVancouverBusinessLicencesAdapter:
    name = "city_vancouver_business_licences"
    family = "directory/regulatory"
    cadence = "daily"
    trust_tier = "official"
    geo_aware = True
    base_url = "https://opendata.vancouver.ca/explore/dataset/business-licences/"
    api_url = "https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/business-licences/records"
    licence = "City of Vancouver Open Data Portal terms"

    def __init__(self, limit: int = 100, client: httpx.Client | None = None) -> None:
        self.limit = limit
        self.client = client or httpx.Client(timeout=30.0)

    def fetch(self) -> list[dict[str, Any]]:
        where = " OR ".join(
            [
                "search(businesstype, 'Health')",
                "search(businesstype, 'Fitness')",
                "search(businesstype, 'Personal Services')",
                "search(businesssubtype, 'Massage')",
                "search(businesssubtype, 'Yoga')",
                "search(businessname, 'Wellness')",
                "search(businesstradename, 'Wellness')",
                "search(businessname, 'Spa')",
                "search(businesstradename, 'Spa')",
                "search(businessname, 'Sauna')",
                "search(businesstradename, 'Sauna')",
                "search(businessname, 'Recovery')",
                "search(businesstradename, 'Recovery')",
            ]
        )
        response = self.client.get(
            self.api_url,
            params={
                "limit": self.limit,
                "where": f"city = 'Vancouver' AND province = 'BC' AND ({where})",
                "order_by": "-extractdate",
            },
        )
        response.raise_for_status()
        payload = response.json()
        return list(payload.get("results", []))

    def source_record_id(self, raw: dict[str, Any]) -> str:
        return str(raw.get("licencersn") or raw.get("licencenumber") or "")

    def normalize(self, raw: dict[str, Any], raw_payload_id: str) -> list[CanonicalOperator]:
        source_record_id = self.source_record_id(raw)
        if not source_record_id:
            return []

        display_name = choose_best_name(raw.get("businesstradename"), raw.get("businessname"))
        categories = normalize_categories(
            raw.get("businessname"),
            raw.get("businesstradename"),
            raw.get("businesstype"),
            raw.get("businesssubtype"),
        )
        if not categories:
            return []

        street_address = compact_address(
            _unit_label(raw),
            compact_address(raw.get("house"), raw.get("street")),
        )
        address = compact_address(
            street_address,
            raw.get("city"),
            raw.get("province"),
            raw.get("postalcode"),
        )
        geo_point = raw.get("geo_point_2d") or {}
        lat = _float_or_none(geo_point.get("lat"))
        lng = _float_or_none(geo_point.get("lon"))
        occurred_at = _occurred_at(raw.get("issueddate"), raw.get("extractdate"))
        source_url = f"{self.base_url}?q={source_record_id}"
        refs = [
            source_ref(
                source_name=self.name,
                url=source_url,
                trust_tier=self.trust_tier,
                source_record_id=source_record_id,
                licence=self.licence,
                seen_at=_parse_datetime(raw.get("extractdate")).isoformat().replace("+00:00", "Z"),
            )
        ]
        status = normalize_status(raw.get("status"))
        confidence = 0.86 if lat is not None and lng is not None else 0.68
        phone = _first_present(
            raw,
            "businessphone",
            "business_phone",
            "contactphone",
            "contact_phone",
            "phone",
            "phone_number",
            "phonenumber",
            "telephone",
        )
        website = _first_present(
            raw,
            "businesswebsite",
            "business_website",
            "website",
            "websiteurl",
            "website_url",
            "webaddress",
            "web_address",
            "businessurl",
            "business_url",
            "url",
        )
        contacts: list[dict[str, Any]] = []
        ref = refs[0]
        for contact_type, value in [("phone", phone), ("website", website)]:
            contact = build_contact_method(
                contact_type=contact_type,
                value=value,
                source_ref=ref,
                confidence=confidence,
            )
            if contact is not None:
                contacts.append(contact)
        normalized_phone = next(
            (str(contact["value"]) for contact in contacts if contact["type"] == "phone"),
            None,
        )
        normalized_website = next(
            (str(contact["value"]) for contact in contacts if contact["type"] == "website"),
            None,
        )
        licensee_name = _clean_business_name(raw.get("businessname"))
        public_contact_candidates = []
        person_candidate = _person_candidate_from_business_name(raw.get("businessname"))
        if person_candidate:
            public_contact_candidates.append(
                {
                    "name": person_candidate,
                    "role": "Public business licence name",
                    "source_ref": ref,
                    "confidence": 0.7,
                }
            )

        return [
            CanonicalOperator(
                id=stable_id("op", self.name, source_record_id),
                source_name=self.name,
                source_record_id=source_record_id,
                raw_payload_id=raw_payload_id,
                name=display_name,
                normalized_name=normalize_name(display_name),
                categories=categories,
                status=status,
                address=address,
                municipality=raw.get("city"),
                province=raw.get("province"),
                country=raw.get("country"),
                neighborhood=raw.get("localarea"),
                lat=lat,
                lng=lng,
                licence_ref=raw.get("licencenumber"),
                source_url=source_url,
                source_refs=refs,
                confidence_score=confidence,
                occurred_at=occurred_at,
                phone=normalized_phone,
                website=normalized_website,
                contacts=contacts,
                payload={
                    "business_type": raw.get("businesstype"),
                    "business_subtype": raw.get("businesssubtype"),
                    "public_licensee_name": licensee_name,
                    "public_contact_candidates": public_contact_candidates,
                    "licence_status": raw.get("status"),
                    "issued_date": raw.get("issueddate"),
                    "expired_date": raw.get("expireddate"),
                    "extract_date": raw.get("extractdate"),
                    "number_of_employees": raw.get("numberofemployees"),
                },
            )
        ]


def _unit_label(raw: dict[str, Any]) -> str | None:
    unit = raw.get("unit")
    if not unit:
        return None
    unit_type = raw.get("unittype") or "Unit"
    return f"{unit_type} {unit}"


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _occurred_at(issued_date: str | None, extract_date: str | None) -> datetime:
    extract_at = _parse_datetime(extract_date)
    if not issued_date:
        return extract_at
    issued_at = _parse_datetime(issued_date)
    if issued_at > extract_at:
        return extract_at
    return issued_at


def _first_present(raw: dict[str, Any], *keys: str) -> Any:
    lowered = {key.lower().replace(" ", "").replace("-", "_"): value for key, value in raw.items()}
    for key in keys:
        direct = raw.get(key)
        if direct is not None and str(direct).strip():
            return direct
        compact_key = key.lower().replace(" ", "").replace("-", "_")
        value = lowered.get(compact_key)
        if value is not None and str(value).strip():
            return value
    return None


def _clean_business_name(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    return text or None


def _person_candidate_from_business_name(value: Any) -> str | None:
    text = _clean_business_name(value)
    if not text:
        return None
    legal_terms = {
        "corp",
        "corporation",
        "inc",
        "incorporated",
        "ltd",
        "limited",
        "llc",
        "company",
        "co",
    }
    words = [word.strip(".,").lower() for word in text.split()]
    if any(word in legal_terms for word in words):
        return None
    if len(words) < 2 or len(words) > 4:
        return None
    return text
