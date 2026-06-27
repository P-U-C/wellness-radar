from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, Literal

from psycopg.types.json import Jsonb

from apps.jobs.runner import DatabaseRepository, RunMetrics
from packages.shared.normalizers import normalize_name

VenueClass = Literal["commercial_wellness", "public_recreation", "unknown"]
OperatorClass = Literal[
    "medical_adjacent",
    "fitness",
    "retail",
    "personal_services",
    "public_recreation",
    "unknown",
]

VENUE_CLASS_COMMERCIAL: VenueClass = "commercial_wellness"
VENUE_CLASS_PUBLIC: VenueClass = "public_recreation"
VENUE_CLASS_UNKNOWN: VenueClass = "unknown"
OPERATOR_CLASS_MEDICAL: OperatorClass = "medical_adjacent"
OPERATOR_CLASS_FITNESS: OperatorClass = "fitness"
OPERATOR_CLASS_RETAIL: OperatorClass = "retail"
OPERATOR_CLASS_PERSONAL: OperatorClass = "personal_services"
OPERATOR_CLASS_PUBLIC: OperatorClass = "public_recreation"
OPERATOR_CLASS_UNKNOWN: OperatorClass = "unknown"
VENUE_CLASSES: tuple[VenueClass, ...] = (
    VENUE_CLASS_COMMERCIAL,
    VENUE_CLASS_PUBLIC,
    VENUE_CLASS_UNKNOWN,
)
OPERATOR_CLASSES: tuple[OperatorClass, ...] = (
    OPERATOR_CLASS_MEDICAL,
    OPERATOR_CLASS_FITNESS,
    OPERATOR_CLASS_RETAIL,
    OPERATOR_CLASS_PERSONAL,
    OPERATOR_CLASS_PUBLIC,
    OPERATOR_CLASS_UNKNOWN,
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
    "aesthetics_medspa",
    "nutrition_longevity",
    "allied_health",
    "womens_health",
    "social_hospitality",
    "recovery_modalities",
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
    "aesthetic",
    "aesthetics",
    "barre",
    "bathhouse",
    "bodywork",
    "botox",
    "boxing",
    "chiro",
    "clinic",
    "cold plunge",
    "compression therapy",
    "contrast",
    "cosmetic",
    "coworking wellness",
    "crossfit",
    "cryotherapy",
    "diagnostic",
    "filler",
    "fitness studio",
    "float",
    "gym",
    "injectable",
    "injectables",
    "infusion",
    "iv",
    "kickboxing",
    "longevity",
    "massage",
    "med spa",
    "medspa",
    "mobility",
    "normatec",
    "naturopath",
    "pilates",
    "physio",
    "recovery",
    "sober social",
    "reformer",
    "sauna",
    "spa",
    "strength",
    "studio",
    "training",
    "wellness",
    "wellness cafe",
    "wellness coworking",
    "yoga",
)
MEDICAL_ADJACENT_KEYWORDS = (
    "acupuncture",
    "aesthetic",
    "aesthetics",
    "botox",
    "chiropractic",
    "chiropractor",
    "clinic",
    "cosmetic medicine",
    "dermatology",
    "diagnostic",
    "filler",
    "fillers",
    "health care",
    "healthcare",
    "injectable",
    "injectables",
    "iv",
    "lactation",
    "laboratory",
    "laser clinic",
    "medical aesthetics",
    "med spa",
    "medspa",
    "microneedling",
    "midwife",
    "midwifery",
    "medical",
    "medical aesthetics",
    "naturopath",
    "naturopathic",
    "pelvic floor",
    "physio",
    "postnatal",
    "postpartum",
    "pregnancy",
    "prenatal",
    "physiotherapist",
    "physiotherapy",
    "rmt",
    "registered massage",
    "screening",
)
FITNESS_KEYWORDS = (
    "barre",
    "boxing",
    "crossfit",
    "fitness",
    "gym",
    "kickboxing",
    "martial arts",
    "pilates",
    "strength",
    "training",
    "weightlifting",
    "yoga",
)
RETAIL_KEYWORDS = (
    "health food",
    "natural product",
    "nutrition supplements",
    "retail",
    "supplement",
    "vitamin store",
)
PERSONAL_SERVICE_KEYWORDS = (
    "bathhouse",
    "cold plunge",
    "compression therapy",
    "contrast",
    "cryotherapy",
    "float",
    "massage",
    "mobility",
    "normatec",
    "percussion therapy",
    "sauna",
    "sober social",
    "spa",
    "steam",
    "thermal",
    "wellness cafe",
    "wellness coworking",
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
        self,
        assignments: Sequence[tuple[str, VenueClass, OperatorClass, bool, dict[str, Any]]],
    ) -> None:
        for operator_id, venue_class, operator_class, regulated, reason in assignments:
            self.conn.execute(
                """
                UPDATE "operator"
                SET venue_class = %s,
                    venue_class_reason = %s,
                    operator_class = %s,
                    regulated = %s,
                    operator_class_reason = %s
                WHERE id = %s
                """,
                (
                    venue_class,
                    Jsonb(reason["venue_class"]),
                    operator_class,
                    regulated,
                    Jsonb(reason["operator_class"]),
                    operator_id,
                ),
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
            classify_operator_class(operator),
            is_regulated_operator(operator),
            classification_reason(operator),
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


def classify_operator_class(operator: dict[str, Any]) -> OperatorClass:
    reason = operator_class_reason(operator)
    scores = reason["scores"]
    ordered = sorted(
        (
            (operator_class, int(scores[operator_class]))
            for operator_class in OPERATOR_CLASSES
            if operator_class != OPERATOR_CLASS_UNKNOWN
        ),
        key=lambda item: (-item[1], item[0]),
    )
    if ordered and ordered[0][1] > 0:
        return ordered[0][0]
    return OPERATOR_CLASS_UNKNOWN


def is_regulated_operator(operator: dict[str, Any]) -> bool:
    return classify_operator_class(operator) == OPERATOR_CLASS_MEDICAL


def classification_reason(operator: dict[str, Any]) -> dict[str, Any]:
    return {
        "venue_class": venue_class_reason(operator),
        "operator_class": operator_class_reason(operator),
    }


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
    commercial_keywords = _matched_keywords(text, COMMERCIAL_KEYWORDS)
    public_keywords = _matched_keywords(text, PUBLIC_KEYWORDS)

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
        "source_refs": _reason_source_refs(operator),
        "scores": {
            VENUE_CLASS_COMMERCIAL: commercial_score,
            VENUE_CLASS_PUBLIC: public_score,
        },
    }


def operator_class_reason(operator: dict[str, Any]) -> dict[str, Any]:
    raw_payloads = _raw_payloads(operator)
    tag_pairs = set(_raw_tag_pairs(raw_payloads))
    text = _evidence_text(operator, raw_payloads, tag_pairs)
    categories = {str(category) for category in operator.get("categories") or []}
    source_names = _source_names(operator.get("source_refs") or [])

    medical_categories = sorted(
        categories.intersection(
            {
                "allied_health",
                "aesthetics_medspa",
                "mental_health",
                "nutrition_longevity",
                "preventive_diagnostic",
                "womens_health",
            }
        )
    )
    fitness_categories = sorted(
        categories.intersection(
            {"climbing", "combat_sports", "fitness_movement", "mind_meditation"}
        )
    )
    retail_categories = sorted(categories.intersection({"wellness_retail_product"}))
    personal_service_categories = sorted(
        categories.intersection(
            {
                "recovery_contrast_therapy",
                "spa_thermal",
                "recovery_modalities",
                "social_hospitality",
            }
        )
    )
    public_categories = sorted(categories.intersection(PUBLIC_CATEGORIES))

    medical_tags = sorted(
        tag_pairs.intersection(
            {
                "healthcare=alternative",
                "healthcare=laboratory",
                "healthcare=massage",
                "healthcare=physiotherapist",
            }
        )
    )
    fitness_tags = sorted(
        tag_pairs.intersection(
            {
                "leisure=fitness_centre",
                "sport=boxing",
                "sport=climbing",
                "sport=crossfit",
                "sport=fitness",
                "sport=martial arts",
                "sport=martial_arts",
                "sport=pilates",
                "sport=weightlifting",
                "sport=yoga",
            }
        )
    )
    retail_tags = sorted(
        tag_pairs.intersection({"shop=health_food", "shop=nutrition_supplements"})
    )
    personal_service_tags = sorted(
        tag_pairs.intersection(
            {
                "amenity=spa",
                "healthcare=massage",
                "leisure=sauna",
                "shop=massage",
            }
        )
    )
    public_tags = sorted(tag_pairs.intersection(PUBLIC_TAGS))

    medical_keywords = _matched_keywords(text, MEDICAL_ADJACENT_KEYWORDS)
    fitness_keywords = _matched_keywords(text, FITNESS_KEYWORDS)
    retail_keywords = _matched_keywords(text, RETAIL_KEYWORDS)
    personal_service_keywords = _matched_keywords(text, PERSONAL_SERVICE_KEYWORDS)
    public_keywords = _matched_keywords(text, PUBLIC_KEYWORDS)

    scores = {
        OPERATOR_CLASS_MEDICAL: (
            4 * len(medical_categories)
            + 5 * len(medical_tags)
            + 3 * len(medical_keywords)
        ),
        OPERATOR_CLASS_FITNESS: (
            4 * len(fitness_categories)
            + 5 * len(fitness_tags)
            + 2 * len(fitness_keywords)
        ),
        OPERATOR_CLASS_RETAIL: (
            4 * len(retail_categories)
            + 5 * len(retail_tags)
            + 2 * len(retail_keywords)
        ),
        OPERATOR_CLASS_PERSONAL: (
            4 * len(personal_service_categories)
            + 5 * len(personal_service_tags)
            + 2 * len(personal_service_keywords)
        ),
        OPERATOR_CLASS_PUBLIC: (
            4 * len(public_categories)
            + 5 * len(public_tags)
            + 2 * len(public_keywords)
        ),
        OPERATOR_CLASS_UNKNOWN: 0,
    }
    return {
        "methodology_version": "operator_class_v1",
        "source_names": source_names,
        "matched_categories": {
            OPERATOR_CLASS_MEDICAL: medical_categories,
            OPERATOR_CLASS_FITNESS: fitness_categories,
            OPERATOR_CLASS_RETAIL: retail_categories,
            OPERATOR_CLASS_PERSONAL: personal_service_categories,
            OPERATOR_CLASS_PUBLIC: public_categories,
        },
        "matched_tags": {
            OPERATOR_CLASS_MEDICAL: medical_tags,
            OPERATOR_CLASS_FITNESS: fitness_tags,
            OPERATOR_CLASS_RETAIL: retail_tags,
            OPERATOR_CLASS_PERSONAL: personal_service_tags,
            OPERATOR_CLASS_PUBLIC: public_tags,
        },
        "matched_keywords": {
            OPERATOR_CLASS_MEDICAL: medical_keywords,
            OPERATOR_CLASS_FITNESS: fitness_keywords,
            OPERATOR_CLASS_RETAIL: retail_keywords,
            OPERATOR_CLASS_PERSONAL: personal_service_keywords,
            OPERATOR_CLASS_PUBLIC: public_keywords,
        },
        "regulated": scores[OPERATOR_CLASS_MEDICAL] > 0,
        "regulated_basis": "medical_adjacent source categories, tags, or public name/licence text",
        "source_refs": _reason_source_refs(operator),
        "scores": scores,
    }


def _source_names(source_refs: Iterable[dict[str, Any]]) -> list[str]:
    names = {
        str(ref.get("source_name") or "").strip()
        for ref in source_refs
        if isinstance(ref, dict) and ref.get("source_name")
    }
    return sorted(name for name in names if name)


def _reason_source_refs(operator: dict[str, Any]) -> list[dict[str, Any]]:
    refs = operator.get("source_refs") or []
    if not isinstance(refs, list):
        return []
    return [ref for ref in refs if isinstance(ref, dict)]


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


def _matched_keywords(text: str, keywords: Iterable[str]) -> list[str]:
    haystack = f" {text} "
    matches: list[str] = []
    for keyword in keywords:
        normalized = normalize_name(keyword)
        if normalized and f" {normalized} " in haystack:
            matches.append(keyword)
    return sorted(matches)


def _key(value: object) -> str:
    return normalize_name(str(value or ""))
