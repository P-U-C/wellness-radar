from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Query

from apps.api.app.db.connection import get_connection
from apps.api.app.services.freshness import age_hours

router = APIRouter(prefix="/api/propositions", tags=["propositions"])


@router.get("")
def propositions(
    category: str | None = Query(default=None),
    geo_level: str | None = Query(default=None, pattern="^(CSD|neighborhood)$"),
    municipality: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    clauses = ["jsonb_array_length(prop.source_refs) > 0"]
    params: list[Any] = []
    if category:
        clauses.append("prop.category = %s")
        params.append(category)
    if geo_level:
        clauses.append("prop.geo_level = %s")
        params.append(geo_level)
    if municipality:
        clauses.append(
            "lower(COALESCE(prop.municipality, prop.geo_name, '')) = lower(%s)"
        )
        params.append(municipality)
    params.append(limit)
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(
                f"""
                SELECT
                  prop.id,
                  prop.heatmap_cell_id,
                  prop.category,
                  prop.geo_code,
                  prop.geo_name,
                  prop.geo_level,
                  prop.municipality,
                  prop.headline,
                  prop.summary,
                  prop.competitor_count_within_radius,
                  prop.competitor_radius_km,
                  prop.population,
                  prop.business_count,
                  prop.demand_source,
                  prop.supporting_signals,
                  prop.component_breakdown,
                  prop.opportunity_score,
                  prop.confidence_score,
                  prop.source_refs,
                  prop.generated_at
                FROM opportunity_proposition prop
                WHERE {' AND '.join(clauses)}
                ORDER BY
                  prop.opportunity_score DESC,
                  prop.confidence_score DESC,
                  prop.geo_level DESC,
                  prop.geo_name ASC
                LIMIT %s
                """,
                params,
            ).fetchall(),
        )
    return {"items": [_proposition_item(row) for row in rows], "meta": {"count": len(rows)}}


def _proposition_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "heatmap_cell_id": row["heatmap_cell_id"],
        "headline": row["headline"],
        "summary": row["summary"],
        "category": row["category"],
        "geo_code": row["geo_code"],
        "geo_name": row["geo_name"],
        "geo_level": row["geo_level"],
        "area": row["geo_name"],
        "municipality": row["municipality"],
        "competitor_count_within_radius": int(row["competitor_count_within_radius"]),
        "competitor_radius_km": float(row["competitor_radius_km"]),
        "population": float(row["population"]) if row["population"] is not None else None,
        "business_count": (
            float(row["business_count"]) if row["business_count"] is not None else None
        ),
        "demand_source": row["demand_source"],
        "supporting_signals": row["supporting_signals"],
        "component_breakdown": row["component_breakdown"],
        "opportunity_score": float(row["opportunity_score"]),
        "confidence": float(row["confidence_score"]),
        "confidence_score": float(row["confidence_score"]),
        "source_refs": row["source_refs"],
        "generated_at": row["generated_at"].isoformat(),
        "freshness_at": row["generated_at"].isoformat(),
        "freshness_age_hours": age_hours(row["generated_at"]),
    }
