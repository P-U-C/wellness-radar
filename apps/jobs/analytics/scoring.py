from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from packages.shared.normalizers import normalize_name

SUPPLY_SATURATION_PER_10000 = 1.0
FALLBACK_NEIGHBORHOOD_SHARE_CAP = 0.25

CITY_VANCOUVER_LOCAL_AREA_PROFILE_REF = {
    "source_name": "city_vancouver_census_local_area_profiles_2016",
    "url": "https://opendata.vancouver.ca/explore/dataset/census-local-area-profiles-2016/",
    "trust_tier": "official",
    "seen_at": "2026-06-26T00:00:00Z",
    "source_record_id": "census-local-area-profiles-2016",
    "licence": "Statistics Canada Census 2016 custom profile via City of Vancouver Open Data",
}


@dataclass(frozen=True)
class NeighborhoodPopulation:
    municipality: str
    neighborhood: str
    population: float
    reference_period: str
    confidence_score: float


def _key(value: object) -> str:
    return normalize_name(str(value or ""))


# Official City of Vancouver 2016 local-area Census profile values used by the
# P0 denominator fix. Keep this table small and reviewed; neighborhoods not in
# this table fall back to a capped CSD estimate that is explicitly flagged.
VANCOUVER_LOCAL_AREA_POPULATIONS: dict[str, NeighborhoodPopulation] = {
    _key("Arbutus Ridge"): NeighborhoodPopulation(
        "Vancouver", "Arbutus Ridge", 15295, "2016 Census", 0.9
    ),
    _key("Downtown"): NeighborhoodPopulation("Vancouver", "Downtown", 62030, "2016 Census", 0.9),
    _key("Dunbar-Southlands"): NeighborhoodPopulation(
        "Vancouver", "Dunbar-Southlands", 21425, "2016 Census", 0.9
    ),
    _key("Fairview"): NeighborhoodPopulation("Vancouver", "Fairview", 33620, "2016 Census", 0.9),
    _key("Hastings-Sunrise"): NeighborhoodPopulation(
        "Vancouver", "Hastings-Sunrise", 34575, "2016 Census", 0.9
    ),
    _key("Kitsilano"): NeighborhoodPopulation("Vancouver", "Kitsilano", 43045, "2016 Census", 0.9),
    _key("Marpole"): NeighborhoodPopulation("Vancouver", "Marpole", 24460, "2016 Census", 0.9),
    _key("Mount Pleasant"): NeighborhoodPopulation(
        "Vancouver", "Mount Pleasant", 32955, "2016 Census", 0.9
    ),
    _key("Oakridge"): NeighborhoodPopulation("Vancouver", "Oakridge", 13030, "2016 Census", 0.9),
    _key("Shaughnessy"): NeighborhoodPopulation(
        "Vancouver", "Shaughnessy", 8430, "2016 Census", 0.9
    ),
}


def supply_sparsity_score(
    density_per_10000: float,
    *,
    saturation_density: float = SUPPLY_SATURATION_PER_10000,
) -> float:
    if density_per_10000 <= 0:
        return 1.0
    if saturation_density <= 0:
        return 0.0
    return _clamp(1 - (density_per_10000 / saturation_density))


def matched_keywords(evidence_text: str, terms: tuple[str, ...]) -> list[str]:
    text = f" {_key(evidence_text)} "
    matches: list[str] = []
    for term in terms:
        normalized = _key(term)
        if normalized and f" {normalized} " in text:
            matches.append(term)
    return matches


def known_neighborhood_population(neighborhood: object) -> NeighborhoodPopulation | None:
    return VANCOUVER_LOCAL_AREA_POPULATIONS.get(_key(neighborhood))


def canonical_municipality_for_neighborhood(
    municipality: object,
    neighborhood: object,
) -> str | None:
    known = known_neighborhood_population(neighborhood)
    if known is not None:
        return known.municipality
    text = str(municipality or "").strip()
    return text or None


def estimated_neighborhood_share(
    *,
    municipality_key: str,
    neighborhood_key: str,
    neighborhood_context: dict[str, Any],
) -> float:
    unique_count = int(
        neighborhood_context.get("unique_neighborhood_counts_by_municipality", {}).get(
            municipality_key, 0
        )
        or 0
    )
    if unique_count <= 0:
        return 0.0
    return _clamp(min(1 / unique_count, FALLBACK_NEIGHBORHOOD_SHARE_CAP))


def dedupe_operators(
    operators: list[dict[str, Any]],
    *,
    distance_km: float = 0.15,
) -> list[dict[str, Any]]:
    survivors: list[dict[str, Any]] = []
    for operator in operators:
        duplicate_index = _find_duplicate_index(survivors, operator, distance_km)
        if duplicate_index is None:
            survivors.append({**operator, "dedupe_cluster_size": 1, "dedupe_duplicate_ids": []})
            continue
        survivors[duplicate_index] = _merge_operator_records(survivors[duplicate_index], operator)
    return sorted(survivors, key=lambda item: str(item.get("name") or "").lower())


def _find_duplicate_index(
    survivors: list[dict[str, Any]],
    operator: dict[str, Any],
    distance_km: float,
) -> int | None:
    for index, survivor in enumerate(survivors):
        if not _same_operator_name(survivor, operator):
            continue
        if _same_address(survivor, operator) or _nearby(survivor, operator, distance_km):
            return index
    return None


def _same_operator_name(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_name = _key(left.get("normalized_name") or left.get("name"))
    right_name = _key(right.get("normalized_name") or right.get("name"))
    return bool(left_name and left_name == right_name)


def _same_address(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_address = _key(left.get("address"))
    right_address = _key(right.get("address"))
    return bool(left_address and left_address == right_address)


def _nearby(left: dict[str, Any], right: dict[str, Any], distance_km: float) -> bool:
    left_lat = _optional_float(left.get("lat"))
    left_lng = _optional_float(left.get("lng"))
    right_lat = _optional_float(right.get("lat"))
    right_lng = _optional_float(right.get("lng"))
    if left_lat is None or left_lng is None or right_lat is None or right_lng is None:
        return False
    return _haversine_km(left_lat, left_lng, right_lat, right_lng) <= distance_km


def _merge_operator_records(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    survivor, duplicate = (
        (left, right) if _operator_rank(left) >= _operator_rank(right) else (right, left)
    )
    duplicate_ids = [
        *list(survivor.get("dedupe_duplicate_ids") or []),
        str(duplicate.get("id")),
        *list(duplicate.get("dedupe_duplicate_ids") or []),
    ]
    merged = {
        **survivor,
        "categories": sorted(
            {str(category) for category in survivor.get("categories") or []}
            | {str(category) for category in duplicate.get("categories") or []}
        ),
        "source_refs": _unique_refs(
            [
                *list(survivor.get("source_refs") or []),
                *list(duplicate.get("source_refs") or []),
            ]
        ),
        "confidence_score": max(
            float(survivor.get("confidence_score") or 0),
            float(duplicate.get("confidence_score") or 0),
        ),
        "dedupe_cluster_size": int(survivor.get("dedupe_cluster_size") or 1)
        + int(duplicate.get("dedupe_cluster_size") or 1),
        "dedupe_duplicate_ids": sorted(set(duplicate_ids)),
    }
    if not merged.get("address"):
        merged["address"] = duplicate.get("address")
    if not merged.get("municipality"):
        merged["municipality"] = duplicate.get("municipality")
    if not merged.get("neighborhood"):
        merged["neighborhood"] = duplicate.get("neighborhood")
    return merged


def _operator_rank(operator: dict[str, Any]) -> tuple[float, int, datetime | str, str]:
    return (
        float(operator.get("confidence_score") or 0),
        len(operator.get("source_refs") or []),
        operator.get("last_seen_at") or operator.get("first_seen_at") or "",
        str(operator.get("id") or ""),
    )


def _unique_refs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict[str, Any]] = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        key = (
            str(ref.get("source_name") or ""),
            str(ref.get("source_record_id") or ""),
            str(ref.get("url") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(ref)
    return unique


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, int | float | str | Decimal):
        return float(value)
    return None


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(
        dlambda / 2
    ) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
