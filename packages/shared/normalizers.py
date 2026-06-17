from __future__ import annotations

import re

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
        "fitness_movement",
        ("fitness", "gym", "pilates", "yoga", "barre", "martial", "dance", "training"),
    ),
    ("mind_meditation", ("meditation", "mindfulness", "breathwork")),
    ("spa_thermal", ("spa", "massage", "esthetic", "esthetician", "steam", "thermal")),
    ("nutrition_longevity", ("nutrition", "dietitian", "longevity", "vitamin")),
    ("womens_health", ("women", "midwife", "maternity", "doula")),
    ("preventive_diagnostic", ("diagnostic", "laboratory", "imaging", "screening")),
    ("mental_health", ("counselling", "counseling", "psychology", "psychologist", "psychotherapy")),
    ("community_social_wellness", ("wellness", "community", "social wellness")),
    ("wellness_retail_product", ("supplement", "natural product", "health food", "retail")),
    (
        "allied_health",
        (
            "health care",
            "chiropractic",
            "physiotherapy",
            "physio",
            "acupuncture",
            "naturopath",
            "kinesiology",
            "clinic",
            "practitioner",
        ),
    ),
]


def normalize_name(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_status(value: str | None) -> str:
    if not value:
        return "unknown"
    return STATUS_MAP.get(value.strip().lower(), "unknown")


def normalize_categories(*values: str | None) -> list[str]:
    text = " ".join(value or "" for value in values).lower()
    categories: list[str] = []
    for category, keywords in CATEGORY_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            categories.append(category)
    if not categories and ("health" in text or "wellness" in text):
        categories.append("allied_health")
    return categories


def compact_address(*parts: str | None) -> str | None:
    cleaned = [part.strip() for part in parts if part and part.strip()]
    if not cleaned:
        return None
    return ", ".join(cleaned)
