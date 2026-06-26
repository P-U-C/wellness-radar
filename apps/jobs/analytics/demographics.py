from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from apps.jobs.analytics.scoring import CITY_VANCOUVER_LOCAL_AREA_PROFILE_REF
from packages.shared.normalizers import normalize_name

TargetDemo = Literal[
    "category_default",
    "broad",
    "young_families",
    "young_adults_20_39",
    "affluent_35_55",
    "retirees_55_plus",
]

TARGET_DEMOS: tuple[TargetDemo, ...] = (
    "category_default",
    "broad",
    "young_families",
    "young_adults_20_39",
    "affluent_35_55",
    "retirees_55_plus",
)

CATEGORY_TARGET_DEMO: dict[str, TargetDemo] = {
    "womens_health": "young_families",
    "yoga_pilates": "young_adults_20_39",
    "fitness_movement": "young_adults_20_39",
    "boutique_strength": "young_adults_20_39",
    "mind_meditation": "young_adults_20_39",
    "community_social_wellness": "young_adults_20_39",
    "social_hospitality": "young_adults_20_39",
    "longevity_iv": "affluent_35_55",
    "nutrition_longevity": "affluent_35_55",
    "preventive_diagnostic": "affluent_35_55",
    "aesthetics_medspa": "affluent_35_55",
    "spa_thermal": "affluent_35_55",
    "allied_health": "broad",
    "recovery_contrast_therapy": "broad",
    "recovery_modalities": "young_adults_20_39",
    "cold_plunge_contrast_therapy": "broad",
}


@dataclass(frozen=True)
class NeighborhoodDemographics:
    municipality: str
    neighborhood: str
    population: float
    age_0_19_pct: float
    age_20_39_pct: float
    age_40_64_pct: float
    age_65_plus_pct: float
    households_with_children_pct: float
    median_household_income: float
    average_household_size: float
    reference_period: str
    confidence_score: float
    source_refs: tuple[dict[str, Any], ...]

    def as_trace(self) -> dict[str, Any]:
        return {
            "source": "city_vancouver_census_local_area_profiles_2016",
            "municipality": self.municipality,
            "neighborhood": self.neighborhood,
            "reference_period": self.reference_period,
            "age_band_distribution": {
                "age_0_19_pct": self.age_0_19_pct,
                "age_20_39_pct": self.age_20_39_pct,
                "age_40_64_pct": self.age_40_64_pct,
                "age_65_plus_pct": self.age_65_plus_pct,
            },
            "households_with_children_pct": self.households_with_children_pct,
            "median_household_income": self.median_household_income,
            "average_household_size": self.average_household_size,
            "confidence_score": self.confidence_score,
        }


def _key(value: object) -> str:
    return normalize_name(str(value or ""))


LOCAL_AREA_PROFILE_SOURCE_REF = {
    **CITY_VANCOUVER_LOCAL_AREA_PROFILE_REF,
    "source_record_id": "census-local-area-profiles-2016-demographics",
}

# Small, reviewed subset of City of Vancouver 2016 local-area Census profile
# fields used by the P2A demand layer. Values stay explicit so scorecards can
# expose which demographic signal moved the demand calculation.
VANCOUVER_LOCAL_AREA_DEMOGRAPHICS: dict[str, NeighborhoodDemographics] = {
    _key("Fairview"): NeighborhoodDemographics(
        municipality="Vancouver",
        neighborhood="Fairview",
        population=33620,
        age_0_19_pct=9.6,
        age_20_39_pct=40.0,
        age_40_64_pct=32.8,
        age_65_plus_pct=17.5,
        households_with_children_pct=18.0,
        median_household_income=69337,
        average_household_size=1.8,
        reference_period="2016 Census",
        confidence_score=0.82,
        source_refs=(LOCAL_AREA_PROFILE_SOURCE_REF,),
    ),
    _key("Kitsilano"): NeighborhoodDemographics(
        municipality="Vancouver",
        neighborhood="Kitsilano",
        population=43045,
        age_0_19_pct=13.3,
        age_20_39_pct=40.1,
        age_40_64_pct=32.8,
        age_65_plus_pct=13.8,
        households_with_children_pct=22.0,
        median_household_income=72839,
        average_household_size=1.9,
        reference_period="2016 Census",
        confidence_score=0.84,
        source_refs=(LOCAL_AREA_PROFILE_SOURCE_REF,),
    ),
    _key("Marpole"): NeighborhoodDemographics(
        municipality="Vancouver",
        neighborhood="Marpole",
        population=24460,
        age_0_19_pct=16.5,
        age_20_39_pct=31.1,
        age_40_64_pct=37.0,
        age_65_plus_pct=15.5,
        households_with_children_pct=35.0,
        median_household_income=53782,
        average_household_size=2.2,
        reference_period="2016 Census",
        confidence_score=0.82,
        source_refs=(LOCAL_AREA_PROFILE_SOURCE_REF,),
    ),
    _key("Mount Pleasant"): NeighborhoodDemographics(
        municipality="Vancouver",
        neighborhood="Mount Pleasant",
        population=32955,
        age_0_19_pct=11.3,
        age_20_39_pct=49.3,
        age_40_64_pct=30.9,
        age_65_plus_pct=8.6,
        households_with_children_pct=19.0,
        median_household_income=66299,
        average_household_size=1.8,
        reference_period="2016 Census",
        confidence_score=0.82,
        source_refs=(LOCAL_AREA_PROFILE_SOURCE_REF,),
    ),
    _key("Shaughnessy"): NeighborhoodDemographics(
        municipality="Vancouver",
        neighborhood="Shaughnessy",
        population=8430,
        age_0_19_pct=20.8,
        age_20_39_pct=23.8,
        age_40_64_pct=34.0,
        age_65_plus_pct=21.6,
        households_with_children_pct=34.0,
        median_household_income=111566,
        average_household_size=2.5,
        reference_period="2016 Census",
        confidence_score=0.82,
        source_refs=(LOCAL_AREA_PROFILE_SOURCE_REF,),
    ),
}


def known_neighborhood_demographics(
    neighborhood: object,
) -> NeighborhoodDemographics | None:
    return VANCOUVER_LOCAL_AREA_DEMOGRAPHICS.get(_key(neighborhood))


def target_demo_for_category(category: str, requested: str | None = None) -> TargetDemo:
    target = _coerce_target_demo(requested)
    if target != "category_default":
        return target
    return CATEGORY_TARGET_DEMO.get(category, "broad")


def demographic_fit_breakdown(
    *,
    category: str,
    geo_name: str,
    business_intensity: float,
    requested_target_demo: str | None = None,
) -> dict[str, Any]:
    resolved_target = target_demo_for_category(category, requested_target_demo)
    demographics = known_neighborhood_demographics(geo_name)
    if demographics is None:
        return _fallback_breakdown(
            category=category,
            target_demo=resolved_target,
            requested_target_demo=requested_target_demo,
            business_intensity=business_intensity,
        )

    normalized = _normalized_demo_scores(demographics)
    weights = _weights_for_target(resolved_target)
    component_scores = _component_scores_for_target(normalized, business_intensity)
    fit = _weighted_score(component_scores, weights, resolved_target)
    return {
        "target_demo": resolved_target,
        "requested_target_demo": requested_target_demo or "category_default",
        "category_default_target_demo": CATEGORY_TARGET_DEMO.get(category, "broad"),
        "source_status": "official_neighborhood_demographics",
        "demographics": demographics.as_trace(),
        "signals": {
            "age_band": _age_signal_for_target(resolved_target),
            "age_score": round(component_scores["age"], 4),
            "family_score": round(component_scores["family"], 4),
            "income_score": round(component_scores["income"], 4),
            "business_intensity_score": round(component_scores["business"], 4),
        },
        "weights": weights,
        "fit": round(fit, 4),
        "source_refs": list(demographics.source_refs),
    }


def demand_proxy_from_population_fit(
    base_population_demand: float,
    target_demo_fit: float,
) -> float:
    return _clamp(0.65 * base_population_demand + 0.35 * target_demo_fit)


def retarget_component_breakdown(
    component_breakdown: Mapping[str, Any],
    requested_target_demo: str | None,
) -> tuple[dict[str, Any], float]:
    target = _coerce_target_demo(requested_target_demo)
    if target == "category_default":
        return dict(component_breakdown), float(component_breakdown.get("opportunity_score") or 0)
    current_components = dict(component_breakdown)
    existing_fit = current_components.get("target_demo_fit_components")
    inputs = current_components.get("inputs")
    if not isinstance(existing_fit, dict) or not isinstance(inputs, dict):
        return current_components, _score_from_components(current_components)
    category = str(inputs.get("category") or current_components.get("category") or "")
    business_intensity = _safe_float(inputs.get("business_density_normalized"), 0.5)
    geo_name = str(inputs.get("geo_name") or "")
    fit = demographic_fit_breakdown(
        category=category,
        geo_name=geo_name,
        business_intensity=business_intensity,
        requested_target_demo=target,
    )
    if fit["source_status"] == "no_neighborhood_demographics":
        return current_components, _score_from_components(current_components)
    base_population_demand = _safe_float(
        inputs.get("base_population_demand"),
        _safe_float(current_components.get("demand_proxy"), 0.0),
    )
    target_demo_fit = float(fit["fit"])
    demand_proxy = demand_proxy_from_population_fit(base_population_demand, target_demo_fit)
    current_components["target_demo_fit"] = round(target_demo_fit, 4)
    current_components["demand_proxy"] = round(demand_proxy, 4)
    current_components["target_demo_fit_components"] = fit
    current_components["retargeted_from"] = existing_fit.get("target_demo")
    if isinstance(inputs, dict):
        inputs["target_demo"] = fit["target_demo"]
        inputs["target_demo_requested"] = fit["requested_target_demo"]
        current_components["inputs"] = inputs
    return current_components, _score_from_components(current_components)


def _normalized_demo_scores(demographics: NeighborhoodDemographics) -> dict[str, float]:
    return {
        "age_0_19": _clamp(demographics.age_0_19_pct / 22.0),
        "age_20_39": _clamp(demographics.age_20_39_pct / 45.0),
        "age_40_64": _clamp(demographics.age_40_64_pct / 38.0),
        "age_65_plus": _clamp(demographics.age_65_plus_pct / 24.0),
        "family": _clamp(demographics.households_with_children_pct / 35.0),
        "income": _clamp((demographics.median_household_income - 45000.0) / 70000.0),
    }


def _component_scores_for_target(
    normalized: Mapping[str, float], business_intensity: float
) -> dict[str, float]:
    return {
        "age": _clamp(
            max(
                normalized["age_0_19"],
                normalized["age_20_39"],
                normalized["age_40_64"],
                normalized["age_65_plus"],
            )
        ),
        "family": _clamp(normalized["family"]),
        "income": _clamp(normalized["income"]),
        "business": _clamp(business_intensity),
        "age_0_19": _clamp(normalized["age_0_19"]),
        "age_20_39": _clamp(normalized["age_20_39"]),
        "age_40_64": _clamp(normalized["age_40_64"]),
        "age_65_plus": _clamp(normalized["age_65_plus"]),
    }


def _weights_for_target(target_demo: TargetDemo) -> dict[str, float]:
    if target_demo == "young_families":
        return {"age": 0.35, "family": 0.45, "income": 0.15, "business": 0.05}
    if target_demo == "young_adults_20_39":
        return {"age": 0.55, "family": 0.05, "income": 0.25, "business": 0.15}
    if target_demo == "affluent_35_55":
        return {"age": 0.25, "family": 0.05, "income": 0.55, "business": 0.15}
    if target_demo == "retirees_55_plus":
        return {"age": 0.55, "family": 0.0, "income": 0.25, "business": 0.20}
    return {"age": 0.25, "family": 0.20, "income": 0.35, "business": 0.20}


def _weighted_score(
    component_scores: Mapping[str, float],
    weights: Mapping[str, float],
    target_demo: TargetDemo,
) -> float:
    age_signal = _age_component_for_target(component_scores, target_demo)
    return _clamp(
        weights["age"] * age_signal
        + weights["family"] * component_scores["family"]
        + weights["income"] * component_scores["income"]
        + weights["business"] * component_scores["business"]
    )


def _age_component_for_target(
    component_scores: Mapping[str, float], target_demo: TargetDemo
) -> float:
    if target_demo == "young_families":
        return component_scores["age_0_19"]
    if target_demo == "young_adults_20_39":
        return component_scores["age_20_39"]
    if target_demo == "retirees_55_plus":
        return component_scores["age_65_plus"]
    if target_demo == "affluent_35_55":
        return component_scores["age_40_64"]
    return component_scores["age"]


def _age_signal_for_target(target_demo: TargetDemo) -> str:
    if target_demo == "young_families":
        return "age_0_19_pct"
    if target_demo == "young_adults_20_39":
        return "age_20_39_pct"
    if target_demo == "affluent_35_55":
        return "age_40_64_pct_as_35_55_proxy"
    if target_demo == "retirees_55_plus":
        return "age_65_plus_pct"
    return "broad_age_distribution"


def _fallback_breakdown(
    *,
    category: str,
    target_demo: TargetDemo,
    requested_target_demo: str | None,
    business_intensity: float,
) -> dict[str, Any]:
    fit = _clamp(0.5 * 0.8 + 0.2 * business_intensity)
    return {
        "target_demo": target_demo,
        "requested_target_demo": requested_target_demo or "category_default",
        "category_default_target_demo": CATEGORY_TARGET_DEMO.get(category, "broad"),
        "source_status": "no_neighborhood_demographics",
        "signals": {
            "age_band": _age_signal_for_target(target_demo),
            "age_score": 0.5,
            "family_score": 0.5,
            "income_score": 0.5,
            "business_intensity_score": round(_clamp(business_intensity), 4),
        },
        "weights": _weights_for_target(target_demo),
        "fit": round(fit, 4),
        "source_refs": [LOCAL_AREA_PROFILE_SOURCE_REF],
    }


def _coerce_target_demo(value: str | None) -> TargetDemo:
    normalized = normalize_name(value or "category_default").replace(" ", "_")
    if normalized in TARGET_DEMOS:
        return normalized
    return "category_default"


def _score_from_components(components: Mapping[str, Any]) -> float:
    return round(
        0.30 * _safe_float(components.get("demand_proxy"), 0.0)
        + 0.20 * _safe_float(components.get("low_supply_density"), 0.0)
        + 0.15 * _safe_float(components.get("category_growth"), 0.0)
        + 0.15 * _safe_float(components.get("target_demo_fit"), 0.0)
        + 0.10 * _safe_float(components.get("transit_access"), 0.0)
        + 0.05 * _safe_float(components.get("event_community_activity"), 0.0)
        + 0.05 * _safe_float(components.get("source_confidence"), 0.0),
        4,
    )


def _safe_float(value: Any, default: float) -> float:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
