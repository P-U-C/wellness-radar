from __future__ import annotations

from typing import Any, cast

from psycopg.types.json import Jsonb

from apps.jobs.analytics.opportunity import COMPETITOR_RADIUS_KM
from apps.jobs.runner import DatabaseRepository, RunMetrics
from packages.shared.ids import stable_id

LEAD_WEDGE_CATEGORIES = [
    "recovery_contrast_therapy",
    "spa_thermal",
    "community_social_wellness",
]

CATEGORY_LABELS = {
    "recovery_contrast_therapy": "recovery and contrast therapy",
    "fitness_movement": "fitness and movement",
    "mind_meditation": "mind and meditation",
    "spa_thermal": "spa and thermal",
    "nutrition_longevity": "nutrition and longevity",
    "allied_health": "allied health",
    "womens_health": "women's health",
    "preventive_diagnostic": "preventive and diagnostic",
    "mental_health": "mental health",
    "community_social_wellness": "community and social wellness",
    "wellness_retail_product": "wellness retail and product",
}


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
                  CASE WHEN cell.category = ANY(%s::text[]) THEN 0 ELSE 1 END,
                  CASE WHEN cell.geo_level = 'neighborhood' THEN 0 ELSE 1 END,
                  cell.opportunity_score DESC,
                  cell.confidence_score DESC,
                  cell.geo_name ASC
                LIMIT %s
                """,
                (LEAD_WEDGE_CATEGORIES, limit),
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
              supporting_signals,
              component_breakdown,
              opportunity_score,
              confidence_score,
              source_refs
            )
            VALUES (
              %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
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
              supporting_signals = EXCLUDED.supporting_signals,
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
                Jsonb(payload["supporting_signals"]),
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
    source_refs = _unique_refs(cast(list[dict[str, Any]], row["source_refs"] or []))
    category = str(row["category"])
    category_label = CATEGORY_LABELS.get(category, category.replace("_", " "))
    area = str(row["geo_name"])
    geo_level = str(row["geo_level"])
    municipality = _municipality(row)
    competitor_count = int(
        trace.get("competitor_count_within_radius") or row["supply_count"] or 0
    )
    radius_km = float(trace.get("competitor_radius_km") or COMPETITOR_RADIUS_KM)
    population = _optional_float(row["population"])
    business_count = _optional_float(row["business_count"])
    demand_source = str(trace.get("demand_source") or "unknown")
    demand_source_status = str(trace.get("demand_source_status") or "unknown")
    confidence = round(_clamp(float(row["confidence_score"])), 4)
    headline = f"Open {category_label} in {area}"
    population_evidence = _population_evidence(population, trace, geo_level, municipality)
    business_evidence = _business_evidence(business_count, trace)
    summary = (
        f"{headline}: {competitor_count} competitor(s) within {radius_km:g} km; "
        f"{population_evidence}; {business_evidence}. "
        f"Opportunity score is {float(row['opportunity_score']):.2f} with "
        f"{confidence:.2f} confidence; demand source is {demand_source_status}."
    )
    supporting_signals = [
        {
            "kind": "competition",
            "label": f"{competitor_count} competitor(s) within {radius_km:g} km",
            "raw_value": competitor_count,
            "radius_km": radius_km,
            "source_refs": source_refs[:5],
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
        "summary": summary,
        "competitor_count_within_radius": competitor_count,
        "competitor_radius_km": radius_km,
        "population": population,
        "business_count": business_count,
        "demand_source": demand_source,
        "supporting_signals": supporting_signals,
        "component_breakdown": {
            "inputs": trace,
            "population_evidence": population_evidence,
            "business_evidence": business_evidence,
            "template": "deterministic-proposition-v1",
        },
        "opportunity_score": float(row["opportunity_score"]),
        "confidence_score": confidence,
        "source_refs": source_refs,
    }


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
