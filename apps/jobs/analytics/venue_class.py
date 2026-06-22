from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, Literal

from psycopg.types.json import Jsonb

from apps.jobs.runner import DatabaseRepository, RunMetrics
from packages.shared.normalizers import normalize_name

VenueClass = Literal["commercial_wellness", "public_recreation", "unknown"]

VENUE_CLASS_COMMERCIAL: VenueClass = "commercial_wellness"
VENUE_CLASS_PUBLIC: VenueClass = "public_recreation"
VENUE_CLASS_UNKNOWN: VenueClass = "unknown"
VENUE_CLASSES: tuple[VenueClass, ...] = (
    VENUE_CLASS_COMMERCIAL,
    VENUE_CLASS_PUBLIC,
    VENUE_CLASS_UNKNOWN,
)

COMMERCIAL_SOURCE_NAMES = {
    "city_vancouver_business_licences",
    "manual_seed",
}
PUBLIC_SOURCE_PREFIXES = ("municipal_facilities",)

COMMERCIAL_CATEGORIES = {
    "recovery_contrast_therapy",
    "fitness_movement",
    "climbing",
    "combat_sports",
    "mind_meditation",
    "spa_thermal",
    "nutrition_longevity",
    "allied_health",
    "womens_health",
    "preventive_diagnostic",
    "mental_health",
    "community_social_wellness",
    "wellness_retail_product",
}
PUBLIC_CATEGORIES = {
    "public_recreation",
    "field_track_sports",
    "racquet_court_sports",
    "aquatics",
    "ice_sports",
}

COMMERCIAL_TAGS = {
    "amenity=gym",
    "amenity=spa",
    "healthcare=alternative",
    "healthcare=laboratory",
    "healthcare=massage",
    "healthcare=physiotherapist",
    "leisure=dance",
    "leisure=fitness_centre",
    "leisure=sauna",
    "shop=health_food",
    "shop=massage",
    "shop=nutrition_supplements",
    "sport=boxing",
    "sport=climbing",
    "sport=crossfit",
    "sport=fitness",
    "sport=martial_arts",
    "sport=martial arts",
    "sport=pilates",
    "sport=weightlifting",
    "sport=yoga",
}
PUBLIC_TAGS = {
    "leisure=fitness_station",
    "leisure=ice_rink",
    "leisure=park",
    "leisure=pitch",
    "leisure=playground",
    "leisure=stadium",
    "leisure=swimming_pool",
    "leisure=track",
    "sport=athletics",
    "sport=badminton",
    "sport=baseball",
    "sport=basketball",
    "sport=cricket",
    "sport=field_hockey",
    "sport=football",
    "sport=hockey",
    "sport=pickleball",
    "sport=rugby",
    "sport=running",
    "sport=soccer",
    "sport=softball",
    "sport=swimming",
    "sport=table_tennis",
    "sport=table tennis",
    "sport=tennis",
    "sport=volleyball",
}
TAG_KEYS = {
    "amenity",
    "court_type",
    "facility_type",
    "field_type",
    "healthcare",
    "leisure",
    "massage",
    "municipal_facility_type",
    "primary_use",
    "shop",
    "sport",
}

COMMERCIAL_KEYWORDS = (
    "acupuncture",
    "barre",
    "bathhouse",
    "bodywork",
    "boxing",
    "chiro",
    "clinic",
    "cold plunge",
    "contrast",
    "crossfit",
    "cryotherapy",
    "diagnostic",
    "fitness studio",
    "float",
    "gym",
    "infusion",
    "iv",
    "kickboxing",
    "longevity",
    "massage",
    "naturopath",
    "pilates",
    "physio",
    "recovery",
    "reformer",
    "sauna",
    "spa",
    "strength",
    "studio",
    "training",
    "wellness",
    "yoga",
)
PUBLIC_KEYWORDS = (
    "aquatic centre",
    "arena",
    "baseball field",
    "community center",
    "community centre",
    "court",
    "field",
    "ice rink",
    "park",
    "pitch",
    "playground",
    "pool",
    "public recreation",
    "recreation center",
    "recreation centre",
    "rink",
    "soccer field",
    "sports field",
    "stadium",
    "tennis court",
    "track",
)

RAW_TEXT_FIELDS = (
    "BUSINESSNAME",
    "DESCRIPTION",
    "MAP_NAME",
    "PARK_NAME",
    "PLACETYPE",
    "PRIMARY_USE",
    "businessdescription",
    "businessname",
    "businesssubtype",
    "businesstradename",
    "businesstype",
    "categories",
    "facility_type",
    "facilitytype",
    "municipal_facility_type",
    "name",
)


class VenueClassRepository(DatabaseRepository):
    def operators_for_venue_classification(self) -> list[dict[str, Any]]:
        return list(
            self.conn.execute(
                """
                SELECT
                  op.id,
                  op.name,
                  op.categories,
                  op.source_refs,
                  raw.raw_payloads
                FROM "operator" op
                LEFT JOIN LATERAL (
                  SELECT COALESCE(jsonb_agg(rp.raw_json), '[]'::jsonb) AS raw_payloads
                  FROM jsonb_array_elements(op.source_refs) AS ref
                  JOIN raw_payload rp
                    ON rp.source_name = ref->>'source_name'
                   AND rp.source_record_id = ref->>'source_record_id'
                ) raw ON TRUE
                WHERE jsonb_array_length(op.source_refs) > 0
                ORDER BY op.name ASC
                """
            ).fetchall()
        )

    def update_operator_venue_classes(
        self, assignments: Sequence[tuple[str, VenueClass, dict[str, Any]]]
    ) -> None:
        for operator_id, venue_class, reason in assignments:
            self.conn.execute(
                """
                UPDATE "operator"
                SET venue_class = %s,
                    venue_class_reason = %s
                WHERE id = %s
                """,
                (venue_class, Jsonb(reason), operator_id),
            )


def run_venue_classification(
    repository: VenueClassRepository | None = None,
) -> RunMetrics:
    repo = repository or VenueClassRepository()
    try:
        return classify_operator_venue_classes(repo)
    finally:
        repo.close()


def classify_operator_venue_classes(repository: VenueClassRepository) -> RunMetrics:
    operators = repository.operators_for_venue_classification()
    assignments = [
        (
            str(operator["id"]),
            classify_operator_venue_class(operator),
            venue_class_reason(operator),
        )
        for operator in operators
    ]
    repository.update_operator_venue_classes(assignments)
    return RunMetrics(records_fetched=len(operators), records_persisted=len(assignments))


def classify_operator_venue_class(operator: dict[str, Any]) -> VenueClass:
    reason = venue_class_reason(operator)
    source_class = reason["source_class"]
    if source_class in VENUE_CLASSES and source_class != VENUE_CLASS_UNKNOWN:
        return source_class

    scores = reason["scores"]
    commercial_score = int(scores["commercial_wellness"])
    public_score = int(scores["public_recreation"])
    if commercial_score > public_score:
        return VENUE_CLASS_COMMERCIAL
    if public_score > commercial_score:
        return VENUE_CLASS_PUBLIC
    if reason["commercial_categories"]:
        return VENUE_CLASS_COMMERCIAL
    if reason["public_categories"]:
        return VENUE_CLASS_PUBLIC
    return VENUE_CLASS_UNKNOWN


def venue_class_reason(operator: dict[str, Any]) -> dict[str, Any]:
    source_names = _source_names(operator.get("source_refs") or [])
    raw_payloads = _raw_payloads(operator)
    tag_pairs = set(_raw_tag_pairs(raw_payloads))
    text = _evidence_text(operator, raw_payloads, tag_pairs)
    categories = {str(category) for category in operator.get("categories") or []}

    commercial_source = any(source in COMMERCIAL_SOURCE_NAMES for source in source_names)
    public_source = any(
        any(source.startswith(prefix) for prefix in PUBLIC_SOURCE_PREFIXES)
        for source in source_names
    )
    source_class: VenueClass = VENUE_CLASS_UNKNOWN
    if commercial_source:
        source_class = VENUE_CLASS_COMMERCIAL
    elif public_source:
        source_class = VENUE_CLASS_PUBLIC

    commercial_categories = sorted(categories.intersection(COMMERCIAL_CATEGORIES))
    public_categories = sorted(categories.intersection(PUBLIC_CATEGORIES))
    commercial_tags = sorted(tag_pairs.intersection(COMMERCIAL_TAGS))
    public_tags = sorted(tag_pairs.intersection(PUBLIC_TAGS))
    commercial_keywords = sorted(keyword for keyword in COMMERCIAL_KEYWORDS if keyword in text)
    public_keywords = sorted(keyword for keyword in PUBLIC_KEYWORDS if keyword in text)

    commercial_score = (
        (5 if commercial_source else 0)
        + 2 * len(commercial_categories)
        + 3 * len(commercial_tags)
        + len(commercial_keywords)
    )
    public_score = (
        (5 if public_source else 0)
        + 2 * len(public_categories)
        + 3 * len(public_tags)
        + len(public_keywords)
    )

    return {
        "methodology_version": "venue_class_v1",
        "source_class": source_class,
        "source_names": source_names,
        "commercial_categories": commercial_categories,
        "public_categories": public_categories,
        "commercial_tags": commercial_tags,
        "public_tags": public_tags,
        "commercial_keywords": commercial_keywords,
        "public_keywords": public_keywords,
        "scores": {
            VENUE_CLASS_COMMERCIAL: commercial_score,
            VENUE_CLASS_PUBLIC: public_score,
        },
    }


def _source_names(source_refs: Iterable[dict[str, Any]]) -> list[str]:
    names = {
        str(ref.get("source_name") or "").strip()
        for ref in source_refs
        if isinstance(ref, dict) and ref.get("source_name")
    }
    return sorted(name for name in names if name)


def _raw_payloads(operator: dict[str, Any]) -> list[dict[str, Any]]:
    payloads = operator.get("raw_payloads") or []
    if not isinstance(payloads, list):
        return []
    return [payload for payload in payloads if isinstance(payload, dict)]


def _raw_tag_pairs(raw_payloads: Sequence[dict[str, Any]]) -> list[str]:
    pairs: set[str] = set()
    for raw in raw_payloads:
        tags = raw.get("tags")
        if isinstance(tags, dict):
            for key in TAG_KEYS:
                value = tags.get(key)
                if value:
                    pairs.add(f"{_key(key)}={_key(value)}")
        for key in TAG_KEYS:
            value = raw.get(key)
            if value:
                pairs.add(f"{_key(key)}={_key(value)}")
    return sorted(pairs)


def _evidence_text(
    operator: dict[str, Any],
    raw_payloads: Sequence[dict[str, Any]],
    tag_pairs: Iterable[str],
) -> str:
    values = [
        str(operator.get("name") or ""),
        " ".join(str(category) for category in operator.get("categories") or []),
        " ".join(tag_pairs),
    ]
    for raw in raw_payloads:
        values.extend(str(raw.get(field) or "") for field in RAW_TEXT_FIELDS)
        tags = raw.get("tags")
        if isinstance(tags, dict):
            values.extend(str(value) for value in tags.values() if value)
    return normalize_name(" ".join(values))


def _key(value: object) -> str:
    return normalize_name(str(value or ""))
