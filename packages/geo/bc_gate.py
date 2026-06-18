from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from psycopg.types.json import Jsonb

BC_BBOX = (-123.30, 49.00, -122.50, 49.40)
BC_PROVINCE_TOKENS = {"bc", "british columbia"}
BC_STATCAN_CODES = {"933", "59"}
WA_ZIP_RE = re.compile(r"\b(9866[0-9]|9867[0-9]|9868[0-6])\b")
WA_NEGATIVE_PATTERNS = [
    re.compile(r"\bvancouver\s*,?\s*wa\b", re.IGNORECASE),
    re.compile(r"\bvancouver\s+washington\b", re.IGNORECASE),
    re.compile(r"\bwashington\b", re.IGNORECASE),
    re.compile(r"\bclark\s+county\b", re.IGNORECASE),
]
POSITIVE_TEXT_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bbc\b",
        r"\bbritish columbia\b",
        r"\bmetro vancouver\b",
        r"\blower mainland\b",
        r"\bvancouver\b",
        r"\bburnaby\b",
        r"\brichmond\b",
        r"\bsurrey\b",
        r"\bnorth vancouver\b",
        r"\bwest vancouver\b",
        r"\bcoquitlam\b",
        r"\bport coquitlam\b",
        r"\bnew westminster\b",
        r"\bdelta\b",
        r"\blangley\b",
        r"\bmaple ridge\b",
        r"\bwhite rock\b",
        r"\bport moody\b",
    ]
]


@dataclass
class CanonicalGeoRecord:
    source_name: str
    title: str | None
    address: str | None
    municipality: str | None
    province: str | None
    country: str | None
    lat: float | None
    lng: float | None
    text: str | None
    statcan_geo_code: str | None
    raw: dict[str, Any]


@dataclass
class GeoGateResult:
    passes: bool
    reason: str | None
    confidence: float


class SQLExecutor(Protocol):
    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> Any:
        ...


def _combined_text(record: CanonicalGeoRecord) -> str:
    return " ".join(
        value
        for value in [
            record.title,
            record.address,
            record.municipality,
            record.province,
            record.country,
            record.text,
            str(record.statcan_geo_code or ""),
        ]
        if value
    )


def _has_negative_wa_token(text: str, province: str | None) -> str | None:
    if province and province.strip().lower() in {"wa", "washington"}:
        return "structured province is Washington"
    if WA_ZIP_RE.search(text):
        return "Washington ZIP code 98660-98686 detected"
    for pattern in WA_NEGATIVE_PATTERNS:
        if pattern.search(text):
            return f"negative Washington token detected: {pattern.pattern}"
    return None


def _coordinate_result(record: CanonicalGeoRecord) -> GeoGateResult | None:
    if record.lat is None and record.lng is None:
        return None
    if record.lat is None or record.lng is None:
        return GeoGateResult(False, "incomplete coordinates", 0.1)
    min_lng, min_lat, max_lng, max_lat = BC_BBOX
    if not (min_lat <= record.lat <= max_lat and min_lng <= record.lng <= max_lng):
        return GeoGateResult(False, "coordinates outside Metro Vancouver bbox", 0.05)
    return GeoGateResult(True, None, 0.72)


def _postgis_boundary_result(
    record: CanonicalGeoRecord, db_session: SQLExecutor | None
) -> GeoGateResult | None:
    if db_session is None or record.lat is None or record.lng is None:
        return None
    try:
        relation_cursor = db_session.execute("SELECT to_regclass('metro_vancouver_boundary')")
        relation = relation_cursor.fetchone()
        if not relation or _first_value(relation) is None:
            return None
        cursor = db_session.execute(
            """
            SELECT EXISTS (
              SELECT 1
              FROM metro_vancouver_boundary
              WHERE ST_Covers(
                geom::geometry,
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)
              )
            )
            """,
            (record.lng, record.lat),
        )
        row = cursor.fetchone()
    except Exception:
        return None
    if row and bool(_first_value(row)):
        return GeoGateResult(True, None, 0.95)
    return GeoGateResult(False, "point outside Metro Vancouver boundary", 0.1)


def _first_value(row: Any) -> Any:
    if isinstance(row, dict):
        return next(iter(row.values()))
    return row[0]


def _has_positive_text(text: str) -> bool:
    return any(pattern.search(text) for pattern in POSITIVE_TEXT_PATTERNS)


def bc_gate(
    record: CanonicalGeoRecord, db_session: SQLExecutor | None = None
) -> GeoGateResult:
    text = _combined_text(record)

    coordinate = _coordinate_result(record)
    if coordinate and not coordinate.passes:
        return coordinate

    negative_reason = _has_negative_wa_token(text, record.province)
    if negative_reason:
        return GeoGateResult(False, negative_reason, 0.01)

    boundary = _postgis_boundary_result(record, db_session)
    if boundary:
        return boundary

    province = (record.province or "").strip().lower()
    if province in BC_PROVINCE_TOKENS:
        confidence = 0.9 if coordinate and coordinate.passes else 0.78
        return GeoGateResult(True, None, confidence)

    if record.statcan_geo_code and str(record.statcan_geo_code).strip() in BC_STATCAN_CODES:
        return GeoGateResult(True, None, 0.88)

    if _has_positive_text(text):
        confidence = 0.8 if coordinate and coordinate.passes else 0.66
        return GeoGateResult(True, None, confidence)

    if coordinate and coordinate.passes:
        return GeoGateResult(False, "coordinates need BC text or boundary confirmation", 0.4)

    return GeoGateResult(False, "no BC location evidence", 0.2)


def log_rejected_record(
    db_session: SQLExecutor,
    record: CanonicalGeoRecord,
    result: GeoGateResult,
    raw_payload_id: str | None,
) -> None:
    db_session.execute(
        """
        INSERT INTO rejected_record (source_name, reason, raw_payload_id, raw)
        VALUES (%s, %s, %s, %s)
        """,
        (
            record.source_name,
            result.reason or "bc_gate rejected record",
            raw_payload_id,
            Jsonb(record.raw),
        ),
    )
