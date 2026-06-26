from __future__ import annotations

import re
from html import unescape
from typing import Any

STATUS_MAP = {
    "issued": "open",
    "pending": "planned",
    "cancelled": "closed",
    "canceled": "closed",
    "gob": "closed",
    "gone out of business": "closed",
    "inactive": "closed",
}

CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    (
        "recovery_contrast_therapy",
        ("sauna", "cold plunge", "contrast", "cryotherapy", "recovery", "float", "bathhouse"),
    ),
    (
        "recovery_modalities",
        (
            "cryo",
            "cryotherapy",
            "normatec",
            "compression therapy",
            "compression boots",
            "percussion therapy",
            "percussive therapy",
            "mobility",
            "sports recovery",
            "assisted stretch",
            "recovery modality",
        ),
    ),
    (
        "fitness_movement",
        ("fitness", "gym", "crossfit", "weightlifting", "dance", "training", "calisthenics"),
    ),
    (
        "racquet_court_sports",
        (
            "pickleball",
            "pickle ball",
            "padel",
            "tennis",
            "squash",
            "badminton",
            "racquet",
            "racket",
            "court",
            "table tennis",
            "ping pong",
        ),
    ),
    ("climbing", ("climbing", "bouldering", "climb")),
    (
        "combat_sports",
        ("boxing", "martial", "martial arts", "martial_arts", "kickboxing", "judo", "karate"),
    ),
    ("aquatics", ("swimming", "swimming pool", "swimming_pool", "aquatic", "pool")),
    ("ice_sports", ("ice rink", "ice_rink", "skating", "hockey", "curling")),
    (
        "field_track_sports",
        (
            "pitch",
            "track",
            "field",
            "soccer",
            "football",
            "baseball",
            "softball",
            "cricket",
            "rugby",
            "stadium",
            "running",
            "athletics",
        ),
    ),
    (
        "public_recreation",
        (
            "community centre",
            "community center",
            "recreation centre",
            "recreation center",
            "sports centre",
            "sports_centre",
            "sports hall",
            "sports_hall",
            "public recreation",
            "park",
            "parks & rec",
            "municipal",
        ),
    ),
    ("mind_meditation", ("meditation", "mindfulness", "breathwork", "yoga", "pilates", "barre")),
    (
        "spa_thermal",
        (
            "esthetic",
            "esthetician",
            "massage",
            "spa",
            "steam",
            "thermal",
        ),
    ),
    (
        "aesthetics_medspa",
        (
            "medical aesthetics",
            "medspa",
            "med spa",
            "botox",
            "injectable",
            "injectables",
            "filler",
            "fillers",
            "cosmetic clinic",
            "cosmetic medicine",
            "skin clinic",
            "skin care clinic",
            "laser clinic",
            "dermatology",
            "microneedling",
            "skin rejuvenation",
            "lymphatic drainage",
        ),
    ),
    (
        "nutrition_longevity",
        ("infusion", "iv", "longevity", "nad", "nutrition", "dietitian", "vitamin"),
    ),
    (
        "womens_health",
        (
            "women",
            "women's health",
            "womens health",
            "midwife",
            "midwifery",
            "maternity",
            "doula",
            "pregnancy",
            "prenatal",
            "postnatal",
            "postpartum",
            "perinatal",
            "pelvic floor",
            "lactation",
            "birth centre",
            "birth center",
        ),
    ),
    ("preventive_diagnostic", ("diagnostic", "laboratory", "imaging", "screening")),
    ("mental_health", ("counselling", "counseling", "psychology", "psychologist", "psychotherapy")),
    ("community_social_wellness", ("wellness", "community", "social wellness")),
    (
        "social_hospitality",
        (
            "sober social",
            "sober club",
            "sober bar",
            "sober curious",
            "wellness cafe",
            "wellness coffee",
            "wellness coworking",
            "wellness co working",
            "coworking wellness",
            "co working wellness",
            "social club",
            "third place wellness",
        ),
    ),
    ("wellness_retail_product", ("supplement", "natural product", "health food", "retail")),
    (
        "allied_health",
        (
            "health care",
            "healthcare",
            "chiropractor",
            "chiropractic",
            "physiotherapist",
            "physiotherapy",
            "physio",
            "acupuncture",
            "acupuncturist",
            "naturopath",
            "naturopathic",
            "kinesiology",
            "kinesiologist",
            "practitioner",
            "rmt",
        ),
    ),
]

METRO_VANCOUVER_MUNICIPALITIES = [
    "Vancouver",
    "Burnaby",
    "New Westminster",
    "Richmond",
    "Delta",
    "Surrey",
    "Langley Township",
    "Langley City",
    "White Rock",
    "Coquitlam",
    "Port Coquitlam",
    "Port Moody",
    "North Vancouver District",
    "North Vancouver City",
    "West Vancouver",
    "Pitt Meadows",
    "Maple Ridge",
]

MOBILE_SERVICE_TERMS = (
    "mobile",
    "at home",
    "at-home",
    "in home",
    "in-home",
    "home visit",
    "house call",
    "on site",
    "onsite",
    "service area",
)

SERVICE_AREA_NEIGHBORHOODS: dict[str, dict[str, str]] = {
    "downtown": {"name": "Downtown", "municipality": "Vancouver"},
    "kitsilano": {"name": "Kitsilano", "municipality": "Vancouver"},
    "mount pleasant": {"name": "Mount Pleasant", "municipality": "Vancouver"},
    "fairview": {"name": "Fairview", "municipality": "Vancouver"},
    "west end": {"name": "West End", "municipality": "Vancouver"},
    "marpole": {"name": "Marpole", "municipality": "Vancouver"},
}


def normalize_name(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_legal_name(value: str) -> str:
    normalized = normalize_name(value)
    suffixes = {
        "bc",
        "co",
        "company",
        "corp",
        "corporation",
        "inc",
        "incorporated",
        "limited",
        "ltd",
        "ulc",
    }
    words = [word for word in normalized.split() if word not in suffixes]
    return " ".join(words)


def normalize_status(value: str | None) -> str:
    if not value:
        return "unknown"
    return STATUS_MAP.get(value.strip().lower(), "unknown")


def normalize_categories(*values: str | None) -> list[str]:
    text = " ".join(value or "" for value in values).lower()
    categories: list[str] = []
    for category, keywords in CATEGORY_KEYWORDS:
        if any(_contains_keyword(text, keyword) for keyword in keywords):
            categories.append(category)
    if not categories and ("health" in text or "wellness" in text):
        categories.append("allied_health")
    return categories


def infer_service_model(*values: str | None) -> tuple[bool, dict[str, Any] | None]:
    raw_text = " ".join(value or "" for value in values)
    text = normalize_name(raw_text)
    matched_terms = [
        term for term in MOBILE_SERVICE_TERMS if _contains_keyword(raw_text, term)
    ]
    if not matched_terms:
        return False, None

    neighborhoods = [
        details
        for key, details in SERVICE_AREA_NEIGHBORHOODS.items()
        if f" {key} " in f" {text} "
    ]
    if "metro vancouver" in text or "lower mainland" in text:
        return True, {
            "type": "metro_region",
            "label": "Metro Vancouver",
            "municipalities": METRO_VANCOUVER_MUNICIPALITIES,
            "neighborhoods": neighborhoods,
            "radius_km": 25.0,
            "matched_terms": matched_terms,
            "methodology_version": "p2b_service_area_keyword_v1",
        }
    if neighborhoods:
        return True, {
            "type": "neighborhoods",
            "label": "Source-stated service neighborhoods",
            "neighborhoods": neighborhoods,
            "matched_terms": matched_terms,
            "methodology_version": "p2b_service_area_keyword_v1",
        }
    return True, {
        "type": "mobile_unspecified",
        "label": "Mobile service area not specified in source text",
        "radius_km": None,
        "matched_terms": matched_terms,
        "methodology_version": "p2b_service_area_keyword_v1",
    }


def _contains_keyword(text: str, keyword: str) -> bool:
    normalized_text = f" {normalize_name(text)} "
    normalized_keyword = normalize_name(keyword)
    return bool(normalized_keyword and f" {normalized_keyword} " in normalized_text)


def compact_address(*parts: str | None) -> str | None:
    cleaned = [part.strip() for part in parts if part and part.strip()]
    if not cleaned:
        return None
    return ", ".join(cleaned)


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(without_tags)).strip()


def truncate_text(value: str, max_len: int = 280) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "..."
