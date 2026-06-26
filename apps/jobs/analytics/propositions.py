from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from psycopg.types.json import Jsonb

from apps.jobs.analytics.opportunity import COMPETITOR_RADIUS_KM
from apps.jobs.runner import DatabaseRepository, RunMetrics
from packages.shared.ids import stable_id

CATEGORY_LABELS = {
    "recovery_contrast_therapy": "recovery and contrast therapy",
    "fitness_movement": "fitness and movement",
    "mind_meditation": "mind and meditation",
    "spa_thermal": "spa and thermal",
    "aesthetics_medspa": "aesthetics and med-spa",
    "nutrition_longevity": "nutrition and longevity",
    "allied_health": "allied health",
    "womens_health": "women's health",
    "social_hospitality": "social hospitality wellness",
    "recovery_modalities": "recovery modalities",
    "preventive_diagnostic": "preventive and diagnostic",
    "mental_health": "mental health",
    "community_social_wellness": "community and social wellness",
    "wellness_retail_product": "wellness retail and product",
}

BC_AVERAGE_HOUSEHOLD_SIZE = 2.4

STATCAN_RECREATION_SPEND_REF = {
    "source_name": "statcan_survey_household_spending",
    "url": "https://www150.statcan.gc.ca/n1/daily-quotidien/250521/dq250521a-eng.htm",
    "trust_tier": "official",
    "seen_at": "2026-06-22T00:00:00Z",
    "source_record_id": "survey-household-spending-2023-recreation",
    "licence": "Statistics Canada terms",
}
STATCAN_PERSONAL_CARE_REF = {
    "source_name": "statcan_personal_care_spending",
    "url": "https://www.statcan.gc.ca/o1/en/plus/5228-getting-ready-go-out",
    "trust_tier": "official",
    "seen_at": "2026-06-22T00:00:00Z",
    "source_record_id": "personal-care-services-2021",
    "licence": "Statistics Canada terms",
}
STATCAN_HOUSEHOLD_SIZE_REF = {
    "source_name": "statcan_census_profile",
    "url": "https://www12.statcan.gc.ca/census-recensement/2021/as-sa/fogs-spg/alternative.cfm?dguid=2021A000259&lang=e&objectId=2&topic=3",
    "trust_tier": "official",
    "seen_at": "2026-06-22T00:00:00Z",
    "source_record_id": "bc-average-household-size-2021",
    "licence": "Statistics Canada terms",
}
CIHI_OUT_OF_POCKET_REF = {
    "source_name": "cihi_nhex",
    "url": "https://www.cihi.ca/sites/default/files/document/health-expenditure-data-in-brief-2024-en.pdf",
    "trust_tier": "official",
    "seen_at": "2026-06-22T00:00:00Z",
    "source_record_id": "out-of-pocket-health-expenditure-per-capita-2022",
    "licence": "CIHI terms",
}


@dataclass(frozen=True)
class SpendProxy:
    label: str
    annual_value: float
    unit: str
    basis: str
    confidence_multiplier: float
    source_refs: list[dict[str, Any]]

    def per_person_value(self) -> float:
        if self.unit == "per_person":
            return self.annual_value
        return self.annual_value / BC_AVERAGE_HOUSEHOLD_SIZE


SPEND_PROXIES: dict[str, SpendProxy] = {
    "recovery_contrast_therapy": SpendProxy(
        label="StatCan 2023 recreation household spend proxy",
        annual_value=5231.0,
        unit="per_household",
        basis=(
            "Average Canadian household recreation spending in 2023; converted to a "
            "per-person proxy with BC 2021 average household size."
        ),
        confidence_multiplier=0.72,
        source_refs=[STATCAN_RECREATION_SPEND_REF, STATCAN_HOUSEHOLD_SIZE_REF],
    ),
    "fitness_movement": SpendProxy(
        label="StatCan 2023 recreation household spend proxy",
        annual_value=5231.0,
        unit="per_household",
        basis=(
            "Average Canadian household recreation spending in 2023; converted to a "
            "per-person proxy with BC 2021 average household size."
        ),
        confidence_multiplier=0.78,
        source_refs=[STATCAN_RECREATION_SPEND_REF, STATCAN_HOUSEHOLD_SIZE_REF],
    ),
    "community_social_wellness": SpendProxy(
        label="StatCan 2023 recreation household spend proxy",
        annual_value=5231.0,
        unit="per_household",
        basis=(
            "Average Canadian household recreation spending in 2023; converted to a "
            "per-person proxy with BC 2021 average household size."
        ),
        confidence_multiplier=0.68,
        source_refs=[STATCAN_RECREATION_SPEND_REF, STATCAN_HOUSEHOLD_SIZE_REF],
    ),
    "spa_thermal": SpendProxy(
        label="StatCan personal care service household spend proxy",
        annual_value=515.0,
        unit="per_household",
        basis=(
            "Average Canadian household hair-grooming service spend reported as the "
            "largest personal-care service line; converted with BC 2021 average "
            "household size."
        ),
        confidence_multiplier=0.66,
        source_refs=[STATCAN_PERSONAL_CARE_REF, STATCAN_HOUSEHOLD_SIZE_REF],
    ),
    "aesthetics_medspa": SpendProxy(
        label="StatCan personal care service household spend proxy",
        annual_value=515.0,
        unit="per_household",
        basis=(
            "Average Canadian household personal-care service spend proxy; med-spa "
            "procedure revenue is not inferred from this value."
        ),
        confidence_multiplier=0.58,
        source_refs=[STATCAN_PERSONAL_CARE_REF, STATCAN_HOUSEHOLD_SIZE_REF],
    ),
    "recovery_modalities": SpendProxy(
        label="StatCan 2023 recreation household spend proxy",
        annual_value=5231.0,
        unit="per_household",
        basis=(
            "Average Canadian household recreation spending in 2023; used only as "
            "context for recovery modality demand."
        ),
        confidence_multiplier=0.66,
        source_refs=[STATCAN_RECREATION_SPEND_REF, STATCAN_HOUSEHOLD_SIZE_REF],
    ),
    "social_hospitality": SpendProxy(
        label="StatCan 2023 recreation household spend proxy",
        annual_value=5231.0,
        unit="per_household",
        basis=(
            "Average Canadian household recreation spending in 2023; cafe, sober, "
            "and coworking wellness capture is not inferred."
        ),
        confidence_multiplier=0.56,
        source_refs=[STATCAN_RECREATION_SPEND_REF, STATCAN_HOUSEHOLD_SIZE_REF],
    ),
    "allied_health": SpendProxy(
        label="CIHI out-of-pocket health expenditure per capita proxy",
        annual_value=1243.4,
        unit="per_person",
        basis=(
            "Canada out-of-pocket health expenditure per capita; broad health-spend "
            "proxy, not allied-health clinic revenue."
        ),
        confidence_multiplier=0.64,
        source_refs=[CIHI_OUT_OF_POCKET_REF],
    ),
}

DEFAULT_SPEND_PROXY = SPEND_PROXIES["recovery_contrast_therapy"]


class PropositionRepository(DatabaseRepository):
    def top_heatmap_cells(self, limit: int) -> list[dict[str, Any]]:
        return list(
            self.conn.execute(
                """
                SELECT
                  cell.id AS heatmap_cell_id,
                  cell.category,
                  cell.geo_code,
                  cell.geo_name,
                  cell.geo_level,
                  cell.supply_count,
                  cell.population,
                  cell.business_count,
                  cell.opportunity_score,
                  cell.confidence_score,
                  cell.component_breakdown,
                  cell.source_refs,
                  cell.trace_payload,
                  parent.geo_name AS parent_geo_name
                FROM opportunity_heatmap_cell cell
                JOIN statcan_geography geo ON geo.geo_code = cell.geo_code
                LEFT JOIN statcan_geography parent ON parent.geo_code = geo.parent_geo_code
                WHERE jsonb_array_length(cell.source_refs) > 0
                  AND cell.geo_level IN ('neighborhood', 'CSD')
                ORDER BY
                  CASE WHEN cell.geo_level = 'neighborhood' THEN 0 ELSE 1 END,
                  cell.opportunity_score DESC,
                  cell.confidence_score DESC,
                  cell.geo_name ASC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
        )

    def upsert_proposition(self, payload: dict[str, Any]) -> None:
        self.conn.execute(
            """
            INSERT INTO opportunity_proposition (
              id,
              heatmap_cell_id,
              category,
              geo_code,
              geo_name,
              geo_level,
              municipality,
              headline,
              summary,
              competitor_count_within_radius,
              competitor_radius_km,
              population,
              business_count,
              demand_source,
              thesis,
              market_sizing_line,
              spend_proxy_label,
              spend_proxy_value,
              nearest_competitors,
              confidence_narrative,
              supporting_signals,
              primary_bundles,
              component_breakdown,
              opportunity_score,
              confidence_score,
              source_refs
            )
            VALUES (
              %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
              %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (category, geo_code) DO UPDATE SET
              heatmap_cell_id = EXCLUDED.heatmap_cell_id,
              geo_name = EXCLUDED.geo_name,
              geo_level = EXCLUDED.geo_level,
              municipality = EXCLUDED.municipality,
              headline = EXCLUDED.headline,
              summary = EXCLUDED.summary,
              competitor_count_within_radius = EXCLUDED.competitor_count_within_radius,
              competitor_radius_km = EXCLUDED.competitor_radius_km,
              population = EXCLUDED.population,
              business_count = EXCLUDED.business_count,
              demand_source = EXCLUDED.demand_source,
              thesis = EXCLUDED.thesis,
              market_sizing_line = EXCLUDED.market_sizing_line,
              spend_proxy_label = EXCLUDED.spend_proxy_label,
              spend_proxy_value = EXCLUDED.spend_proxy_value,
              nearest_competitors = EXCLUDED.nearest_competitors,
              confidence_narrative = EXCLUDED.confidence_narrative,
              supporting_signals = EXCLUDED.supporting_signals,
              primary_bundles = EXCLUDED.primary_bundles,
              component_breakdown = EXCLUDED.component_breakdown,
              opportunity_score = EXCLUDED.opportunity_score,
              confidence_score = EXCLUDED.confidence_score,
              source_refs = EXCLUDED.source_refs,
              generated_at = now()
            """,
            (
                payload["id"],
                payload["heatmap_cell_id"],
                payload["category"],
                payload["geo_code"],
                payload["geo_name"],
                payload["geo_level"],
                payload["municipality"],
                payload["headline"],
                payload["summary"],
                payload["competitor_count_within_radius"],
                payload["competitor_radius_km"],
                payload["population"],
                payload["business_count"],
                payload["demand_source"],
                payload["thesis"],
                payload["market_sizing_line"],
                payload["spend_proxy_label"],
                payload["spend_proxy_value"],
                Jsonb(payload["nearest_competitors"]),
                payload["confidence_narrative"],
                Jsonb(payload["supporting_signals"]),
                payload["primary_bundles"],
                Jsonb(payload["component_breakdown"]),
                payload["opportunity_score"],
                payload["confidence_score"],
                Jsonb(payload["source_refs"]),
            ),
        )


def run_proposition_synthesis(
    repository: PropositionRepository | None = None,
    *,
    limit: int = 50,
) -> RunMetrics:
    repo = repository or PropositionRepository()
    metrics = RunMetrics()
    try:
        rows = repo.top_heatmap_cells(limit)
        metrics.records_fetched = len(rows)
        for row in rows:
            proposition = proposition_from_heatmap_cell(row)
            if not proposition["source_refs"]:
                continue
            repo.upsert_proposition(proposition)
            metrics.records_persisted += 1
        repo.conn.commit()
        return metrics
    finally:
        repo.close()


def proposition_from_heatmap_cell(row: dict[str, Any]) -> dict[str, Any]:
    trace = cast(dict[str, Any], row["trace_payload"] or {})
    score_components = cast(dict[str, Any], row.get("component_breakdown") or {})
    source_refs = _unique_refs(cast(list[dict[str, Any]], row["source_refs"] or []))
    category = str(row["category"])
    category_label = CATEGORY_LABELS.get(category, category.replace("_", " "))
    area = str(row["geo_name"])
    geo_level = str(row["geo_level"])
    municipality = _municipality(row)
    nearest_competitors = _nearest_competitors(trace)
    competitor_count = int(trace.get("competitor_count_within_radius") or len(nearest_competitors))
    radius_km = float(trace.get("competitor_radius_km") or COMPETITOR_RADIUS_KM)
    population = _optional_float(row["population"])
    business_count = _optional_float(row["business_count"])
    demand_source = str(trace.get("demand_source") or "unknown")
    demand_source_status = str(trace.get("demand_source_status") or "unknown")
    spend_proxy = SPEND_PROXIES.get(category, DEFAULT_SPEND_PROXY)
    spend_proxy_value = spend_proxy.per_person_value()
    target_demo_fit = _optional_float(score_components.get("target_demo_fit"))
    target_demo = str(trace.get("target_demo") or "category_default")
    primary_bundles = [
        str(bundle)
        for bundle in trace.get("primary_bundles", [])
        if str(bundle).strip()
    ]
    market_size = (
        (population or 0.0) * spend_proxy_value * (target_demo_fit or 1.0)
        if population is not None
        else None
    )
    confidence = _proposition_confidence(float(row["confidence_score"]), trace, spend_proxy)
    headline = f"{area}: source-backed {category_label} whitespace"
    population_evidence = _population_evidence(population, trace, geo_level, municipality)
    business_evidence = _business_evidence(business_count, trace)
    market_sizing_line = _market_sizing_line(
        population=population,
        proxy=spend_proxy,
        per_person_value=spend_proxy_value,
        market_size=market_size,
        target_demo=target_demo,
        target_demo_fit=target_demo_fit,
    )
    competitor_line = _competitor_line(nearest_competitors, competitor_count, radius_km)
    confidence_narrative = _confidence_narrative(
        confidence=confidence,
        row_confidence=float(row["confidence_score"]),
        trace=trace,
        spend_proxy=spend_proxy,
        competitor_count=competitor_count,
    )
    thesis = (
        f"{headline}. {market_sizing_line} {competitor_line} "
        f"{population_evidence}; {business_evidence}. {confidence_narrative}"
    )
    source_refs = _unique_refs(
        [
            *source_refs,
            *spend_proxy.source_refs,
            *[
                ref
                for competitor in nearest_competitors
                for ref in competitor.get("source_refs", [])
            ],
        ]
    )
    supporting_signals = [
        {
            "kind": "competition",
            "label": competitor_line,
            "raw_value": competitor_count,
            "radius_km": radius_km,
            "competitors": nearest_competitors[:8],
            "source_refs": _competition_refs(nearest_competitors, source_refs),
        },
        {
            "kind": "market_sizing",
            "label": market_sizing_line,
            "raw_value": round(market_size, 2) if market_size is not None else None,
            "proxy_value_per_person": round(spend_proxy_value, 2),
            "target_demo": target_demo,
            "target_demo_fit": target_demo_fit,
            "source_refs": spend_proxy.source_refs,
        },
        {
            "kind": "population",
            "label": population_evidence,
            "raw_value": population,
            "source_refs": source_refs[:5],
        },
        {
            "kind": "business_count",
            "label": business_evidence,
            "raw_value": business_count,
            "source_refs": source_refs[:5],
        },
        {
            "kind": "demand_provenance",
            "label": f"{demand_source} / {demand_source_status}",
            "raw_value": demand_source,
            "source_refs": source_refs[:5],
        },
        {
            "kind": "confidence",
            "label": confidence_narrative,
            "raw_value": confidence,
            "source_refs": source_refs[:5],
        },
    ]
    return {
        "id": stable_id("prop", category, row["geo_code"]),
        "heatmap_cell_id": row["heatmap_cell_id"],
        "category": category,
        "geo_code": row["geo_code"],
        "geo_name": area,
        "geo_level": geo_level,
        "municipality": municipality,
        "headline": headline,
        "summary": thesis,
        "competitor_count_within_radius": competitor_count,
        "competitor_radius_km": radius_km,
        "population": population,
        "business_count": business_count,
        "demand_source": demand_source,
        "thesis": thesis,
        "market_sizing_line": market_sizing_line,
        "spend_proxy_label": spend_proxy.label,
        "spend_proxy_value": round(spend_proxy_value, 4),
        "nearest_competitors": nearest_competitors,
        "confidence_narrative": confidence_narrative,
        "supporting_signals": supporting_signals,
        "primary_bundles": primary_bundles,
        "component_breakdown": {
            "inputs": trace,
            "population_evidence": population_evidence,
            "business_evidence": business_evidence,
            "market_sizing_line": market_sizing_line,
            "target_demo": target_demo,
            "target_demo_fit": target_demo_fit,
            "primary_bundles": primary_bundles,
            "nearest_competitors": nearest_competitors,
            "confidence_narrative": confidence_narrative,
            "spend_proxy": {
                "label": spend_proxy.label,
                "basis": spend_proxy.basis,
                "annual_value": spend_proxy.annual_value,
                "unit": spend_proxy.unit,
                "per_person_value": round(spend_proxy_value, 4),
                "confidence_multiplier": spend_proxy.confidence_multiplier,
                "source_refs": spend_proxy.source_refs,
            },
            "template": "deterministic-proposition-v2",
        },
        "opportunity_score": float(row["opportunity_score"]),
        "confidence_score": confidence,
        "source_refs": source_refs,
    }


def _nearest_competitors(trace: dict[str, Any]) -> list[dict[str, Any]]:
    raw_competitors = trace.get("nearest_competitors")
    if not isinstance(raw_competitors, list):
        return []
    competitors: list[dict[str, Any]] = []
    for item in raw_competitors:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        operator_id = str(item.get("operator_id") or "").strip()
        if not name or not operator_id:
            continue
        competitors.append(
            {
                "operator_id": operator_id,
                "name": name,
                "distance_km": _optional_float(item.get("distance_km")),
                "municipality": item.get("municipality"),
                "neighborhood": item.get("neighborhood"),
                "source_refs": _unique_refs(
                    cast(list[dict[str, Any]], item.get("source_refs") or [])
                ),
            }
        )
    return competitors


def _market_sizing_line(
    *,
    population: float | None,
    proxy: SpendProxy,
    per_person_value: float,
    market_size: float | None,
    target_demo: str,
    target_demo_fit: float | None,
) -> str:
    demo_clause = (
        f" x target-demo fit {target_demo_fit:.2f} ({target_demo})"
        if target_demo_fit is not None
        else ""
    )
    if population is None or market_size is None:
        return (
            f"Catchment spend context: unknown catchment population x "
            f"{_format_money(per_person_value)} per-person {proxy.label.lower()}"
            f"{demo_clause}; "
            "context unavailable until the population denominator is present."
        )
    return (
        f"Catchment spend context: {_format_number(population, 'people')} x "
        f"{_format_money(per_person_value)} per-person {proxy.label.lower()}"
        f"{demo_clause} = "
        f"{_format_money(market_size)} of annual household spending in the catchment "
        "(context for demand, not capturable revenue)."
    )


def _competitor_line(
    competitors: list[dict[str, Any]],
    competitor_count: int,
    radius_km: float,
) -> str:
    if competitors:
        names = ", ".join(str(item["name"]) for item in competitors[:5])
        extra = competitor_count - len(competitors[:5])
        suffix = f", plus {extra} more" if extra > 0 else ""
        return (
            f"Nearest named competitors within {radius_km:g} km: {names}{suffix} "
            f"({competitor_count} total)."
        )
    if competitor_count:
        return (
            f"{competitor_count} same-category competitor(s) were counted within "
            f"{radius_km:g} km, but no source-backed names were available in the trace."
        )
    return f"No named same-category competitors were found within {radius_km:g} km."


def _competition_refs(
    competitors: list[dict[str, Any]],
    fallback_refs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    refs = _unique_refs(
        [ref for competitor in competitors for ref in competitor.get("source_refs", [])]
    )
    return refs[:8] if refs else fallback_refs[:5]


def _proposition_confidence(
    row_confidence: float,
    trace: dict[str, Any],
    spend_proxy: SpendProxy,
) -> float:
    confidence = _clamp(row_confidence) * spend_proxy.confidence_multiplier
    if "fixture" in str(trace.get("demand_source_status") or trace.get("demand_source")):
        confidence *= 0.92
    if str(trace.get("denominator_scope") or "CSD") != "CSD":
        confidence *= 0.88
    return round(_clamp(confidence), 4)


def _confidence_narrative(
    *,
    confidence: float,
    row_confidence: float,
    trace: dict[str, Any],
    spend_proxy: SpendProxy,
    competitor_count: int,
) -> str:
    modifiers: list[str] = [f"base score confidence {row_confidence:.2f}"]
    if "fixture" in str(trace.get("demand_source_status") or trace.get("demand_source")):
        modifiers.append("demand denominator is fixture-backed")
    if str(trace.get("denominator_scope") or "CSD") != "CSD":
        status = str(trace.get("population_estimation_status") or "estimated")
        if status == "official_neighborhood":
            modifiers.append("neighborhood population uses official local-area data")
        else:
            modifiers.append("neighborhood values are estimated from parent CSD denominators")
    modifiers.append(f"spend proxy is broad ({spend_proxy.label})")
    if competitor_count == 0:
        modifiers.append("no named competitors were found in-radius")
    else:
        modifiers.append(f"{competitor_count} named/countable competitor input(s)")
    return f"Confidence {confidence:.2f}: " + "; ".join(modifiers) + "."


def _municipality(row: dict[str, Any]) -> str | None:
    if row["geo_level"] == "neighborhood":
        return str(row["parent_geo_name"]) if row.get("parent_geo_name") else None
    return str(row["geo_name"])


def _population_evidence(
    population: float | None,
    trace: dict[str, Any],
    geo_level: str,
    municipality: str | None,
) -> str:
    formatted = _format_number(population, "people")
    if geo_level == "neighborhood":
        status = str(trace.get("population_estimation_status") or "estimated")
        method = str(trace.get("population_estimation_method") or "").strip()
        if status == "official_neighborhood":
            suffix = f" ({method})" if method else ""
            return f"{formatted} official local-area population{suffix}"
        parent_population = _format_number(
            _optional_float(trace.get("raw_parent_population")), "people"
        )
        share = _optional_float(trace.get("population_allocation_share"))
        share_label = f"{share * 100:.1f}%" if share is not None else "an observed"
        return (
            f"{formatted} estimated neighborhood population from {share_label} share "
            f"of {municipality or 'parent CSD'} ({parent_population})"
        )
    return f"{formatted} CSD population"


def _business_evidence(business_count: float | None, trace: dict[str, Any]) -> str:
    scope = str(trace.get("denominator_scope") or "CSD")
    if scope != "CSD":
        parent_business = _format_number(
            _optional_float(trace.get("raw_parent_business_count")), "business locations"
        )
        return (
            f"{_format_number(business_count, 'business locations')} estimated category "
            f"business count from parent CSD raw count {parent_business}"
        )
    return f"{_format_number(business_count, 'business locations')} category business count"


def _format_number(value: float | None, unit: str) -> str:
    if value is None:
        return f"unknown {unit}"
    if value >= 1000:
        return f"{value:,.0f} {unit}"
    if value == int(value):
        return f"{int(value)} {unit}"
    return f"{value:.1f} {unit}"


def _format_money(value: float) -> str:
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1000:
        return f"${value:,.0f}"
    return f"${value:.0f}"


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, str | int | float):
        return float(value)
    try:
        return float(cast(Any, value))  # Decimal and other numeric DB values.
    except (TypeError, ValueError):
        return None


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _unique_refs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for ref in refs:
        key = "|".join(str(ref.get(field)) for field in ("source_name", "url", "source_record_id"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(ref)
    return unique
