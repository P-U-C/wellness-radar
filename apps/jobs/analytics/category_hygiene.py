from __future__ import annotations

from typing import Any

from apps.jobs.analytics.scoring import matched_keywords
from packages.shared.normalizers import normalize_name

NAME_DENY_BY_BUNDLE: dict[str, tuple[str, ...]] = {
    "cold_plunge_contrast_therapy": (
        "together we can drug alcohol recovery",
        "coast mental health road to recovery",
    ),
    "spa_thermal": (
        "milano nail spa",
        "third space counselling",
        "third space contracting",
    ),
    "boutique_strength": ("dragon temple martial arts",),
    "longevity_iv": (
        "cougar crag",
        "tombstone tower",
        "well of poison area",
        "knuckle head",
    ),
}

NAME_DENY_BY_CATEGORY: dict[str, tuple[str, ...]] = {
    "recovery_contrast_therapy": NAME_DENY_BY_BUNDLE["cold_plunge_contrast_therapy"],
    "spa_thermal": NAME_DENY_BY_BUNDLE["spa_thermal"],
    "nutrition_longevity": NAME_DENY_BY_BUNDLE["longevity_iv"],
    "preventive_diagnostic": NAME_DENY_BY_BUNDLE["longevity_iv"],
}

COLD_MODALITY_TERMS = (
    "cold plunge",
    "contrast",
    "kontrast",
    "cryo",
    "cryotherapy",
    "float",
    "sauna",
    "bathhouse",
    "recovery room",
)
REHAB_TERMS = (
    "addiction",
    "drug",
    "alcohol",
    "mental health",
    "rehab",
    "rehabilitation",
    "recovery society",
    "road to recovery",
)
SPA_EXCLUSION_TERMS = (
    "nail",
    "nails",
    "manicure",
    "pedicure",
    "counselling",
    "counseling",
    "contracting",
    "contractor",
    "construction",
)
LONGEVITY_EXCLUSION_TERMS = (
    "bouldering",
    "climbing",
    "crag",
    "tower",
    "golf",
    "f45",
    "chiro",
    "chiropractic",
    "fitness",
    "martial arts",
)
LONGEVITY_POSITIVE_TERMS = (
    "longevity",
    "iv",
    "infusion",
    "nad",
    "vitamin",
    "diagnostic",
    "laboratory",
)
STRENGTH_EXCLUSION_TERMS = (
    "martial arts",
    "karate",
    "judo",
    "boxing",
    "kickboxing",
    "yoga",
    "pilates",
    "barre",
    "dance",
)
STRENGTH_POSITIVE_TERMS = (
    "strength",
    "gym",
    "fitness",
    "training",
    "crossfit",
    "conditioning",
    "weightlifting",
)


def bundle_match_is_allowed(
    slug: str,
    operator: dict[str, Any],
    match_reasons: dict[str, Any],
    evidence_text: str,
) -> bool:
    name = str(operator.get("name") or "")
    if _name_denied(slug, name):
        return False
    if slug == "cold_plunge_contrast_therapy":
        return _cold_match_allowed(match_reasons, evidence_text)
    if slug == "spa_thermal":
        return not _has_any(evidence_text, SPA_EXCLUSION_TERMS)
    if slug == "longevity_iv":
        return _longevity_match_allowed(match_reasons, evidence_text)
    if slug == "boutique_strength":
        return _strength_match_allowed(match_reasons, evidence_text)
    return True


def category_operator_is_allowed(category: str, operator: dict[str, Any]) -> bool:
    evidence_text = _operator_text(operator)
    name = str(operator.get("name") or "")
    if _category_name_denied(category, name):
        return False
    if category == "recovery_contrast_therapy":
        return _has_any(evidence_text, COLD_MODALITY_TERMS) or not _has_any(
            evidence_text, REHAB_TERMS
        )
    if category == "spa_thermal":
        return not _has_any(evidence_text, SPA_EXCLUSION_TERMS)
    if category in {"nutrition_longevity", "preventive_diagnostic"}:
        if _has_any(evidence_text, LONGEVITY_EXCLUSION_TERMS):
            return False
        return _has_any(evidence_text, LONGEVITY_POSITIVE_TERMS) or category == (
            "preventive_diagnostic"
        )
    return True


def _cold_match_allowed(match_reasons: dict[str, Any], evidence_text: str) -> bool:
    has_modality = bool(
        set(match_reasons.get("tag_matches") or [])
        or _has_any(evidence_text, COLD_MODALITY_TERMS)
    )
    if _has_any(evidence_text, REHAB_TERMS) and not has_modality:
        return False
    return has_modality


def _longevity_match_allowed(match_reasons: dict[str, Any], evidence_text: str) -> bool:
    if _has_any(evidence_text, LONGEVITY_EXCLUSION_TERMS):
        return False
    return bool(
        set(match_reasons.get("tag_matches") or [])
        or _has_any(evidence_text, LONGEVITY_POSITIVE_TERMS)
    )


def _strength_match_allowed(match_reasons: dict[str, Any], evidence_text: str) -> bool:
    if _has_any(evidence_text, STRENGTH_EXCLUSION_TERMS):
        return False
    return bool(
        set(match_reasons.get("tag_matches") or [])
        or _has_any(evidence_text, STRENGTH_POSITIVE_TERMS)
    )


def _name_denied(slug: str, name: str) -> bool:
    normalized = normalize_name(name)
    return any(denied in normalized for denied in NAME_DENY_BY_BUNDLE.get(slug, ()))


def _category_name_denied(category: str, name: str) -> bool:
    normalized = normalize_name(name)
    return any(denied in normalized for denied in NAME_DENY_BY_CATEGORY.get(category, ()))


def _has_any(evidence_text: str, terms: tuple[str, ...]) -> bool:
    return bool(matched_keywords(evidence_text, terms))


def _operator_text(operator: dict[str, Any]) -> str:
    values = [
        str(operator.get("name") or ""),
        str(operator.get("address") or ""),
        str(operator.get("municipality") or ""),
        str(operator.get("neighborhood") or ""),
        " ".join(str(category) for category in operator.get("categories") or []),
    ]
    return normalize_name(" ".join(values))
