from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any

import httpx

from packages.schemas.canonical import SignalRecord, SourceEventRecord
from packages.shared.ids import stable_id
from packages.shared.provenance import source_ref

PACKAGE_SEARCH_URL = "https://catalogue.data.gov.bc.ca/api/3/action/package_search"
DEFAULT_RESOURCE_URL = (
    "https://catalogue.data.gov.bc.ca/dataset/c6893289-f99c-4d03-a891-9de6805fa9ba/"
    "resource/8e1ca199-f23d-4c7d-8f91-d7e8b572250f/download/"
    "bus_location_counts_cdcsd.csv"
)
DEFAULT_PACKAGE_URL = "https://catalogue.data.gov.bc.ca/dataset/number-of-businesses"
DEFAULT_RESOURCE_ID = "8e1ca199-f23d-4c7d-8f91-d7e8b572250f"
METRO_VAN_CD_NAME = "Metro Vancouver"


class BCDataCatalogueAdapter:
    name = "bc_data_catalogue"
    family = "denominator/context"
    cadence = "annual/as_released"
    trust_tier = "official"
    geo_aware = True
    base_url = "https://catalogue.data.gov.bc.ca/"
    licence = "Open Government Licence - British Columbia"

    def __init__(self, limit: int = 100, client: httpx.Client | None = None) -> None:
        self.limit = limit
        self.client = client or httpx.Client(
            timeout=60.0,
            follow_redirects=True,
            headers={"user-agent": "wellness-radar/0.1", "accept": "application/json,*/*"},
        )

    def fetch(self) -> list[dict[str, Any]]:
        package = self._find_number_of_businesses_package()
        resource = _find_csd_csv_resource(package) or {
            "id": DEFAULT_RESOURCE_ID,
            "url": DEFAULT_RESOURCE_URL,
            "name": "Business Locations by Census Subdivision (CSV)",
        }
        response = self.client.get(str(resource["url"]))
        response.raise_for_status()
        records = _metro_vancouver_records_from_csv(response.text)
        source_url = str(package.get("url") or DEFAULT_PACKAGE_URL)
        licence = str(package.get("license_title") or self.licence)
        return [
            {
                **record,
                "_package_name": package.get("name") or "number-of-businesses",
                "_package_title": package.get("title") or "Number of Businesses",
                "_source_url": source_url,
                "_resource_id": resource.get("id"),
                "_resource_name": resource.get("name"),
                "_resource_url": resource.get("url"),
                "_licence": licence,
            }
            for record in records[: self.limit]
        ]

    def _find_number_of_businesses_package(self) -> dict[str, Any]:
        response = self.client.get(
            PACKAGE_SEARCH_URL,
            params={"q": "number of businesses", "rows": 10},
        )
        response.raise_for_status()
        result = response.json().get("result", {})
        for package in result.get("results", []):
            if package.get("name") == "number-of-businesses":
                return dict(package)
        return {
            "name": "number-of-businesses",
            "title": "Number of Businesses",
            "url": DEFAULT_PACKAGE_URL,
            "license_title": self.licence,
            "resources": [],
        }

    def source_record_id(self, raw: dict[str, Any]) -> str:
        return f"{raw.get('_package_name', 'number-of-businesses')}:{raw.get('CDCSD Code')}"

    def normalize(
        self, raw: dict[str, Any], raw_payload_id: str
    ) -> list[tuple[SourceEventRecord, SignalRecord]]:
        source_record_id = self.source_record_id(raw)
        year = str(raw.get("_reference_year") or "2024")
        occurred_at = datetime(int(year), 12, 31, tzinfo=timezone.utc)
        csd_name = _clean_csd_name(raw.get("CSD Name"))
        geo_code = str(raw.get("CDCSD Code") or "")
        grand_total = _int_or_none(raw.get("Grand Total"))
        with_employees = _int_or_none(raw.get("Sub-Total With Employees"))
        if not csd_name or not geo_code or grand_total is None:
            return []

        refs = [
            source_ref(
                source_name=self.name,
                url=str(raw.get("_source_url") or DEFAULT_PACKAGE_URL),
                trust_tier=self.trust_tier,
                source_record_id=source_record_id,
                licence=str(raw.get("_licence") or self.licence),
                seen_at=occurred_at.isoformat().replace("+00:00", "Z"),
            )
        ]
        title = f"BC Stats business locations count for {csd_name}"
        payload = {
            "dataset_title": raw.get("_package_title"),
            "resource_id": raw.get("_resource_id"),
            "resource_name": raw.get("_resource_name"),
            "resource_url": raw.get("_resource_url"),
            "geo_code": geo_code,
            "geo_level": "CSD",
            "geo_name": csd_name,
            "cd_name": raw.get("CD Name"),
            "development_region": raw.get("DR Name"),
            "reference_period": year,
            "grand_total_business_locations": grand_total,
            "business_locations_with_employees": with_employees,
            "business_locations_no_employees": _int_or_none(raw.get("No Employees*")),
            "employment_size_counts": _employment_size_counts(raw),
            "bc_gate_text": f"{csd_name}, Metro Vancouver, British Columbia, BC",
        }
        event = SourceEventRecord(
            id=stable_id("evt", self.name, source_record_id, "bc_business_count_csd"),
            source_name=self.name,
            raw_payload_id=raw_payload_id,
            source_record_id=source_record_id,
            event_type="bc_business_count_csd",
            entity_type=None,
            entity_id=None,
            title=title,
            occurred_at=occurred_at,
            trust_tier=self.trust_tier,
            lat=None,
            lng=None,
            source_refs=refs,
            confidence_score=0.9,
            payload=payload,
        )
        if with_employees is not None:
            summary = (
                f"BC Stats reports {grand_total:,} business locations in {csd_name} "
                f"for {year}; {with_employees:,} have employees."
            )
        else:
            summary = (
                f"BC Stats reports {grand_total:,} business locations in "
                f"{csd_name} for {year}."
            )
        signal = SignalRecord(
            id=stable_id("sig", self.name, source_record_id, "bc_business_count_context"),
            type="bc_business_count_context",
            severity="info",
            title=title,
            summary=summary,
            why_it_matters=(
                "Adds official BC Stats business-density context for Metro Vancouver CSDs."
            ),
            source_name=self.name,
            source_url=str(raw.get("_source_url") or DEFAULT_PACKAGE_URL),
            trust_tier=self.trust_tier,
            occurred_at=occurred_at,
            lat=None,
            lng=None,
            related_operator_id=None,
            source_event_ids=[event.id],
            raw_payload_id=raw_payload_id,
            source_refs=refs,
            confidence_score=0.9,
        )
        return [(event, signal)]


def _find_csd_csv_resource(package: dict[str, Any]) -> dict[str, Any] | None:
    for resource in package.get("resources", []):
        name = str(resource.get("name") or "")
        fmt = str(resource.get("format") or "").lower()
        if "Census Subdivision" in name and fmt == "csv" and resource.get("url"):
            return dict(resource)
    return None


def _metro_vancouver_records_from_csv(csv_text: str) -> list[dict[str, Any]]:
    rows = list(csv.reader(io.StringIO(csv_text.lstrip("\ufeff"))))
    header_index = next(
        index for index, row in enumerate(rows) if row and row[0].strip() == "CDCSD Code"
    )
    reference_year = _reference_year(rows[:header_index])
    header = rows[header_index]
    records: list[dict[str, Any]] = []
    for row in rows[header_index + 1 :]:
        if not row or len(row) < len(header):
            continue
        record = dict(zip(header, row, strict=False))
        if record.get("CD Name") != METRO_VAN_CD_NAME:
            continue
        record["_reference_year"] = reference_year
        records.append(record)
    return records


def _reference_year(preamble_rows: list[list[str]]) -> str:
    for row in preamble_rows:
        text = " ".join(cell for cell in row if cell)
        if "British Columbia Business Counts by Employee Size" in text:
            for token in text.replace(",", " ").split():
                if token.isdigit() and len(token) == 4:
                    return token
    return str(datetime.now(timezone.utc).year - 1)


def _employment_size_counts(raw: dict[str, Any]) -> dict[str, int]:
    labels = [
        "1 to 4",
        "5 to 9",
        "10 to 19",
        "20 to 49",
        "50 to 99",
        "100 to 199",
        "200 to 499",
        "500 to 999",
        "1,000 to 1,499",
        "1,500 to 2,499",
        "2,500 to 4,999",
        "5,000 and over",
    ]
    return {label: value for label in labels if (value := _int_or_none(raw.get(label))) is not None}


def _int_or_none(value: Any) -> int | None:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _clean_csd_name(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text.rsplit(" (", 1)[0].strip()
