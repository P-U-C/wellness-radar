from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Query

from apps.api.app.db.connection import get_connection

router = APIRouter(prefix="/analytics", tags=["analytics"])

REQUIRED_OPPORTUNITY_COMPONENTS = {
    "demand_proxy",
    "low_supply_density",
    "category_growth",
    "target_demo_fit",
    "transit_access",
    "event_community_activity",
    "source_confidence",
}


@router.get("/whitespace")
def whitespace_heatmap(
    category: str = Query(default="recovery_contrast_therapy"),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(
                """
                SELECT
                  id,
                  category,
                  geo_code,
                  geo_name,
                  geo_level,
                  ST_Y(geom::geometry) AS lat,
                  ST_X(geom::geometry) AS lng,
                  supply_count,
                  operator_ids,
                  population,
                  business_count,
                  opportunity_score,
                  component_breakdown,
                  calculation_method,
                  source_refs,
                  confidence_score,
                  trace_payload,
                  generated_at
                FROM opportunity_heatmap_cell
                WHERE category = %s
                  AND jsonb_array_length(source_refs) > 0
                  AND component_breakdown ?& %s::text[]
                  AND component_breakdown->>'source_confidence' IS NOT NULL
                ORDER BY opportunity_score DESC, geo_name ASC
                LIMIT %s
                """,
                (category, list(REQUIRED_OPPORTUNITY_COMPONENTS), limit),
            ).fetchall(),
        )
    return {"items": [_heatmap_item(row) for row in rows], "meta": {"count": len(rows)}}


@router.get("/opportunity-scorecards")
def opportunity_scorecards(
    category: str = Query(default="recovery_contrast_therapy"),
    limit: int = Query(default=10, ge=1, le=100),
) -> dict[str, Any]:
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(
                """
                SELECT
                  id,
                  category,
                  geo_code,
                  geo_name,
                  opportunity_score,
                  component_breakdown,
                  source_refs,
                  confidence_score,
                  calculation_method,
                  caveat,
                  generated_at
                FROM opportunity_scorecard
                WHERE category = %s
                  AND jsonb_array_length(source_refs) > 0
                  AND component_breakdown ?& %s::text[]
                  AND component_breakdown->>'source_confidence' IS NOT NULL
                ORDER BY opportunity_score DESC, geo_name ASC
                LIMIT %s
                """,
                (category, list(REQUIRED_OPPORTUNITY_COMPONENTS), limit),
            ).fetchall(),
        )
    return {"items": [_scorecard_item(row) for row in rows], "meta": {"count": len(rows)}}


@router.get("/category-velocity")
def category_velocity(
    category: str | None = Query(default=None),
) -> dict[str, Any]:
    clauses = ["jsonb_array_length(source_refs) > 0"]
    params: list[Any] = []
    if category:
        clauses.append("category = %s")
        params.append(category)
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(
                f"""
                SELECT
                  id,
                  category,
                  window_days,
                  new_operator_count,
                  job_velocity_count,
                  event_velocity_count,
                  news_velocity_count,
                  component_breakdown,
                  source_refs,
                  confidence_score,
                  calculated_at
                FROM category_velocity
                WHERE {' AND '.join(clauses)}
                ORDER BY category ASC, window_days ASC
                """,
                params,
            ).fetchall(),
        )
    return {"items": [_velocity_item(row) for row in rows], "meta": {"count": len(rows)}}


@router.get("/methodology")
def analytics_methodology() -> dict[str, Any]:
    return {
        "opportunity": {
            "formula": (
                "0.30 demand_proxy + 0.20 low_supply_density + 0.15 category_growth "
                "+ 0.15 target_demo_fit + 0.10 transit_access + "
                "0.05 event_community_activity + 0.05 source_confidence"
            ),
            "caveat": (
                "White-space is a source-backed supply-demand signal, not guaranteed "
                "economic attractiveness."
            ),
            "requires": [
                "component_breakdown",
                "source_refs",
                "source_confidence",
            ],
        },
        "influence": {
            "formula": (
                "0.25 institutional_authority + 0.20 network_centrality + "
                "0.15 research_or_clinical_leadership + 0.15 media_velocity + "
                "0.10 capital_power + 0.10 event_convening + 0.05 public_reach, "
                "with locality multiplier, recency decay, and source confidence."
            ),
            "governance": (
                "Public professional data only; no private, patient, LinkedIn, "
                "or social-firehose data."
            ),
        },
    }


def _heatmap_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "category": row["category"],
        "geo_code": row["geo_code"],
        "geo_name": row["geo_name"],
        "geo_level": row["geo_level"],
        "lat": float(row["lat"]) if row["lat"] is not None else None,
        "lng": float(row["lng"]) if row["lng"] is not None else None,
        "supply_count": row["supply_count"],
        "operator_ids": row["operator_ids"],
        "population": float(row["population"]) if row["population"] is not None else None,
        "business_count": (
            float(row["business_count"]) if row["business_count"] is not None else None
        ),
        "opportunity_score": float(row["opportunity_score"]),
        "component_breakdown": row["component_breakdown"],
        "calculation_method": row["calculation_method"],
        "source_refs": row["source_refs"],
        "confidence_score": float(row["confidence_score"]),
        "trace_payload": row["trace_payload"],
        "generated_at": row["generated_at"].isoformat(),
    }


def _scorecard_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "category": row["category"],
        "geo_code": row["geo_code"],
        "geo_name": row["geo_name"],
        "opportunity_score": float(row["opportunity_score"]),
        "component_breakdown": row["component_breakdown"],
        "source_refs": row["source_refs"],
        "confidence_score": float(row["confidence_score"]),
        "calculation_method": row["calculation_method"],
        "caveat": row["caveat"],
        "generated_at": row["generated_at"].isoformat(),
    }


def _velocity_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "category": row["category"],
        "window_days": row["window_days"],
        "new_operator_count": row["new_operator_count"],
        "job_velocity_count": row["job_velocity_count"],
        "event_velocity_count": row["event_velocity_count"],
        "news_velocity_count": row["news_velocity_count"],
        "component_breakdown": row["component_breakdown"],
        "source_refs": row["source_refs"],
        "confidence_score": float(row["confidence_score"]),
        "calculated_at": row["calculated_at"].isoformat(),
    }
