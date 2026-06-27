from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from packages.schemas.canonical import CanonicalOperator
from packages.shared.contacts import build_contact_method
from packages.shared.ids import stable_id
from packages.shared.normalizers import infer_service_model, normalize_name
from packages.shared.provenance import source_ref

DEFAULT_SEED_PATH = (
    Path(__file__).resolve().parents[3] / "db" / "seeds" / "manual_recovery_operators.csv"
)


class ManualRecoverySeedAdapter:
    name = "manual_seed"
    family = "directory/seed"
    cadence = "manual"
    trust_tier = "informal"
    geo_aware = True
    dedupe_existing = True
    licence = "source-specific public pages"

    def __init__(self, path: Path | None = None, limit: int = 100) -> None:
        self.path = path or DEFAULT_SEED_PATH
        self.limit = limit

    def fetch(self) -> list[dict[str, Any]]:
        with self.path.open(newline="") as handle:
            return list(csv.DictReader(handle))[: self.limit]

    def source_record_id(self, raw: dict[str, Any]) -> str:
        return str(raw.get("source_record_id") or normalize_name(str(raw.get("name") or "")))

    def normalize(self, raw: dict[str, Any], raw_payload_id: str) -> list[CanonicalOperator]:
        name = str(raw.get("name") or "").strip()
        if not name:
            return []
        source_record_id = self.source_record_id(raw)
        categories = [
            category.strip()
            for category in str(raw.get("categories") or "").split("|")
            if category.strip()
        ]
        is_mobile, service_area = infer_service_model(
            name,
            raw.get("categories"),
            raw.get("notes"),
            raw.get("service_area"),
        )
        refs = [
            source_ref(
                source_name=self.name,
                url=raw.get("source_url"),
                trust_tier=self.trust_tier,
                source_record_id=source_record_id,
                licence=self.licence,
            )
        ]
        website_contact = build_contact_method(
            contact_type="website",
            value=raw.get("website") or raw.get("source_url"),
            source_ref=refs[0],
            confidence=_float_or_none(raw.get("confidence_score")) or 0.6,
        )
        contacts = [website_contact] if website_contact else []
        website = str(website_contact["value"]) if website_contact else None
        return [
            CanonicalOperator(
                id=stable_id("op", self.name, source_record_id),
                source_name=self.name,
                source_record_id=source_record_id,
                raw_payload_id=raw_payload_id,
                name=name,
                normalized_name=normalize_name(name),
                categories=categories or ["recovery_contrast_therapy"],
                status=str(raw.get("status") or "open"),
                address=raw.get("address"),
                municipality=raw.get("municipality"),
                province=raw.get("province"),
                country=raw.get("country"),
                neighborhood=raw.get("neighborhood"),
                lat=_float_or_none(raw.get("lat")),
                lng=_float_or_none(raw.get("lng")),
                licence_ref=None,
                source_url=raw.get("source_url") or raw.get("website"),
                source_refs=refs,
                confidence_score=_float_or_none(raw.get("confidence_score")) or 0.6,
                occurred_at=datetime.now(timezone.utc),
                is_mobile=is_mobile,
                service_area=service_area,
                website=website,
                contacts=contacts,
                payload={
                    "website": raw.get("website"),
                    "notes": raw.get("notes"),
                    "event_type": "manual_seed_operator",
                    "signal_type": "operator_seed",
                    "signal_title": f"Manual recovery seed: {name}",
                    "signal_summary": (
                        f"{name} was added to the private-alpha recovery/contrast operator seed."
                    ),
                    "trust_tier": self.trust_tier,
                },
            )
        ]


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
