from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Query

from apps.api.app.db.connection import get_connection
from apps.api.app.services.freshness import age_hours
from apps.jobs.analytics.demographics import TARGET_DEMOS, retarget_component_breakdown

router = APIRouter(prefix="/analytics", tags=["analytics"])
MAX_WHITESPACE_LIMIT = 500
MAX_SCORECARD_LIMIT = 100
MAX_PROXIMITY_LIMIT = 250
TARGET_DEMO_PATTERN = (
    "^(category_default|broad|young_families|young_adults_20_39|"
    "affluent_35_55|retirees_55_plus)$"
)

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
    geo_level: str | None = Query(default=None, pattern="^(CSD|neighborhood)$"),
    target_demo: str = Query(default="category_default", pattern=TARGET_DEMO_PATTERN),
    limit: int = Query(default=100, ge=1),
) -> dict[str, Any]:
    active_limit = min(limit, MAX_WHITESPACE_LIMIT)
    fetch_limit = MAX_WHITESPACE_LIMIT if target_demo != "category_default" else active_limit
    clauses = [
        "category = %s",
        "jsonb_array_length(source_refs) > 0",
        "component_breakdown ?& %s::text[]",
        "component_breakdown->>'source_confidence' IS NOT NULL",
    ]
    params: list[Any] = [category, list(REQUIRED_OPPORTUNITY_COMPONENTS)]
    if geo_level:
        clauses.append("geo_level = %s")
        params.append(geo_level)
    params.append(fetch_limit)
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(
                f"""
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
                WHERE {' AND '.join(clauses)}
                ORDER BY opportunity_score DESC, geo_name ASC
                LIMIT %s
                """,
                params,
            ).fetchall(),
        )
    return {
        "items": _ranked_heatmap_items(rows, target_demo=target_demo, limit=active_limit),
        "meta": {
            "count": min(len(rows), active_limit),
            "limit": active_limit,
            "requested_limit": limit,
            "max_limit": MAX_WHITESPACE_LIMIT,
            "target_demo": target_demo,
            "available_target_demos": list(TARGET_DEMOS),
        },
    }


@router.get("/opportunity-scorecards")
def opportunity_scorecards(
    category: str = Query(default="recovery_contrast_therapy"),
    geo_level: str | None = Query(default=None, pattern="^(CSD|neighborhood)$"),
    target_demo: str = Query(default="category_default", pattern=TARGET_DEMO_PATTERN),
    limit: int = Query(default=10, ge=1),
) -> dict[str, Any]:
    active_limit = min(limit, MAX_SCORECARD_LIMIT)
    fetch_limit = MAX_SCORECARD_LIMIT if target_demo != "category_default" else active_limit
    clauses = [
        "category = %s",
        "jsonb_array_length(source_refs) > 0",
        "component_breakdown ?& %s::text[]",
        "component_breakdown->>'source_confidence' IS NOT NULL",
    ]
    params: list[Any] = [category, list(REQUIRED_OPPORTUNITY_COMPONENTS)]
    if geo_level:
        clauses.append("geo_level = %s")
        params.append(geo_level)
    params.append(fetch_limit)
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(
                f"""
                SELECT
                  id,
                  category,
                  geo_code,
                  geo_name,
                  geo_level,
                  opportunity_score,
                  component_breakdown,
                  source_refs,
                  confidence_score,
                  calculation_method,
                  caveat,
                  generated_at
                FROM opportunity_scorecard
                WHERE {' AND '.join(clauses)}
                ORDER BY opportunity_score DESC, geo_name ASC
                LIMIT %s
                """,
                params,
            ).fetchall(),
        )
    return {
        "items": _ranked_scorecard_items(rows, target_demo=target_demo, limit=active_limit),
        "meta": {
            "count": min(len(rows), active_limit),
            "limit": active_limit,
            "requested_limit": limit,
            "max_limit": MAX_SCORECARD_LIMIT,
            "target_demo": target_demo,
            "available_target_demos": list(TARGET_DEMOS),
        },
    }


@router.get("/category-velocity")
def category_velocity(
    category: str | None = Query(default=None),
) -> dict[str, Any]:
    clauses = ["jsonb_array_length(COALESCE(cv.source_refs, base.taxonomy_source_refs)) > 0"]
    params: list[Any] = []
    if category:
        clauses.append("base.category = %s")
        params.append(category)
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(
                f"""
                WITH populated_categories AS (
                  SELECT DISTINCT category.category
                  FROM "operator" op
                  CROSS JOIN LATERAL unnest(op.categories) AS category(category)
                  WHERE jsonb_array_length(op.source_refs) > 0
                  UNION
                  SELECT DISTINCT category
                  FROM category_velocity
                  WHERE jsonb_array_length(source_refs) > 0
                ),
                windows(window_days) AS (
                  VALUES (30), (90), (180)
                ),
                base AS (
                  SELECT
                    pc.category,
                    windows.window_days,
                    taxonomy.source_refs AS taxonomy_source_refs
                  FROM populated_categories pc
                  CROSS JOIN windows
                  JOIN category_taxonomy taxonomy
                    ON taxonomy.category = pc.category
                )
                SELECT
                  COALESCE(cv.id, 'velocity_' || base.category || '_' || base.window_days)
                    AS id,
                  base.category,
                  base.window_days,
                  COALESCE(cv.new_operator_count, 0) AS new_operator_count,
                  COALESCE(cv.job_velocity_count, 0) AS job_velocity_count,
                  COALESCE(cv.event_velocity_count, 0) AS event_velocity_count,
                  COALESCE(cv.news_velocity_count, 0) AS news_velocity_count,
                  COALESCE(
                    cv.component_breakdown,
                    jsonb_build_object(
                      'new_operator_count', 0,
                      'job_velocity_count', 0,
                      'event_velocity_count', 0,
                      'news_velocity_count', 0,
                      'window_days', base.window_days,
                      'source_confidence', 0.5,
                      'method',
                      'No persisted velocity row yet; explicit zero counts for '
                      || 'a source-backed operator category.'
                    )
                  ) AS component_breakdown,
                  COALESCE(cv.source_refs, base.taxonomy_source_refs) AS source_refs,
                  COALESCE(cv.confidence_score, 0.5) AS confidence_score,
                  COALESCE(cv.calculated_at, now()) AS calculated_at
                FROM base
                LEFT JOIN category_velocity cv
                  ON cv.category = base.category
                 AND cv.window_days = base.window_days
                WHERE {' AND '.join(clauses)}
                ORDER BY base.category ASC, base.window_days ASC
                """,
                params,
            ).fetchall(),
        )
    return {"items": [_velocity_item(row) for row in rows], "meta": {"count": len(rows)}}


@router.get("/proximity")
def operator_proximity(
    category: str = Query(default="recovery_modalities"),
    near_category: str = Query(default="fitness_movement"),
    radius_km: float = Query(default=1.0, ge=0.1, le=25.0),
    limit: int = Query(default=100, ge=1),
) -> dict[str, Any]:
    active_limit = min(limit, MAX_PROXIMITY_LIMIT)
    radius_m = radius_km * 1000
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(
                """
                WITH subject AS (
                  SELECT
                    op.id,
                    op.name,
                    op.categories,
                    op.municipality,
                    op.neighborhood,
                    op.source_refs,
                    op.confidence_score,
                    op.geom
                  FROM "operator" op
                  WHERE %s = ANY(op.categories)
                    AND op.geom IS NOT NULL
                    AND jsonb_array_length(op.source_refs) > 0
                ),
                nearby AS (
                  SELECT
                    subject.id AS subject_id,
                    ref.id AS operator_id,
                    ref.name,
                    ref.categories,
                    ref.municipality,
                    ref.neighborhood,
                    ST_Distance(subject.geom, ref.geom) / 1000.0 AS distance_km,
                    ref.source_refs,
                    ref.confidence_score
                  FROM subject
                  JOIN "operator" ref
                    ON ref.id <> subject.id
                   AND %s = ANY(ref.categories)
                   AND ref.geom IS NOT NULL
                   AND jsonb_array_length(ref.source_refs) > 0
                   AND ST_DWithin(subject.geom, ref.geom, %s)
                )
                SELECT
                  subject.id,
                  subject.name,
                  subject.categories,
                  subject.municipality,
                  subject.neighborhood,
                  ST_Y(subject.geom::geometry) AS lat,
                  ST_X(subject.geom::geometry) AS lng,
                  subject.source_refs,
                  subject.confidence_score,
                  count(nearby.operator_id)::int AS nearby_count,
                  min(nearby.distance_km) AS min_distance_km,
                  COALESCE(
                    jsonb_agg(
                      jsonb_build_object(
                        'operator_id', nearby.operator_id,
                        'name', nearby.name,
                        'categories', nearby.categories,
                        'municipality', nearby.municipality,
                        'neighborhood', nearby.neighborhood,
                        'distance_km', round(nearby.distance_km::numeric, 3),
                        'source_refs', nearby.source_refs,
                        'confidence_score', nearby.confidence_score
                      )
                      ORDER BY nearby.distance_km ASC, nearby.name ASC
                    ) FILTER (WHERE nearby.operator_id IS NOT NULL),
                    '[]'::jsonb
                  ) AS nearby_operators
                FROM subject
                JOIN nearby ON nearby.subject_id = subject.id
                GROUP BY
                  subject.id,
                  subject.name,
                  subject.categories,
                  subject.municipality,
                  subject.neighborhood,
                  subject.geom,
                  subject.source_refs,
                  subject.confidence_score
                ORDER BY nearby_count DESC, min_distance_km ASC, subject.name ASC
                LIMIT %s
                """,
                [category, near_category, radius_m, active_limit],
            ).fetchall(),
        )
    return {
        "items": [
            _proximity_item(row, radius_km=radius_km, near_category=near_category)
            for row in rows
        ],
        "meta": {
            "count": len(rows),
            "category": category,
            "near_category": near_category,
            "radius_km": radius_km,
            "limit": active_limit,
            "requested_limit": limit,
            "max_limit": MAX_PROXIMITY_LIMIT,
        },
    }


@router.get("/methodology")
def analytics_methodology() -> dict[str, Any]:
    return {
        "opportunity": {
            "formula": (
                "0.30 demand_proxy + 0.20 low_supply_density + 0.15 category_growth "
                "+ 0.15 target_demo_fit + 0.10 transit_access + "
                "0.05 event_community_activity + 0.05 source_confidence"
            ),
            "supply_component": (
                "low_supply_density is computed from deduped same-category operators per "
                "10,000 population using a saturation curve. Dense mature categories score "
                "down instead of being rewarded for relative rank inside their own category. "
                "Mobile/service-area operators count against declared service municipalities "
                "or neighborhoods rather than only a storefront point."
            ),
            "demand_component": (
                "P2A demand_proxy blends population scale with target_demo_fit where "
                "reviewed City of Vancouver local-area Census demographic attributes are "
                "available. target_demo_fit is decomposed into age-band, family-density, "
                "income, and business-intensity signals and can be retargeted with the "
                "target_demo query parameter."
            ),
            "target_demo_options": list(TARGET_DEMOS),
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
        "bundles": {
            "formula": (
                "0.30 demand_proxy + 0.15 member_scale + 0.25 low_supply_density + "
                "0.20 momentum + 0.10 source_confidence"
            ),
            "relationship_to_whitespace": (
                "Bundles and whitespace use the same deduped per-capita supply saturation "
                "component. Bundles summarize category-level attractiveness; whitespace "
                "scores a category in a specific geography."
            ),
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
        "proximity": {
            "formula": (
                "operator proximity score = max(0, 1 - nearest_reference_distance_km / "
                "radius_km); rows are source-backed operators within the requested "
                "radius of a source-backed reference category."
            ),
            "caveat": (
                "Co-location is a proximity thesis input, not proof of partnership "
                "or demand."
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
        "freshness_at": row["generated_at"].isoformat(),
        "freshness_age_hours": age_hours(row["generated_at"]),
    }


def _scorecard_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "category": row["category"],
        "geo_code": row["geo_code"],
        "geo_name": row["geo_name"],
        "geo_level": row["geo_level"],
        "opportunity_score": float(row["opportunity_score"]),
        "component_breakdown": row["component_breakdown"],
        "source_refs": row["source_refs"],
        "confidence_score": float(row["confidence_score"]),
        "calculation_method": row["calculation_method"],
        "caveat": row["caveat"],
        "generated_at": row["generated_at"].isoformat(),
        "freshness_at": row["generated_at"].isoformat(),
        "freshness_age_hours": age_hours(row["generated_at"]),
    }


def _ranked_heatmap_items(
    rows: list[dict[str, Any]],
    *,
    target_demo: str,
    limit: int,
) -> list[dict[str, Any]]:
    items = [_with_retargeted_score(_heatmap_item(row), target_demo) for row in rows]
    return sorted(
        items,
        key=lambda item: (-float(item["opportunity_score"]), str(item["geo_name"]).lower()),
    )[:limit]


def _ranked_scorecard_items(
    rows: list[dict[str, Any]],
    *,
    target_demo: str,
    limit: int,
) -> list[dict[str, Any]]:
    items = [_with_retargeted_score(_scorecard_item(row), target_demo) for row in rows]
    return sorted(
        items,
        key=lambda item: (-float(item["opportunity_score"]), str(item["geo_name"]).lower()),
    )[:limit]


def _with_retargeted_score(item: dict[str, Any], target_demo: str) -> dict[str, Any]:
    if target_demo == "category_default":
        return item
    components, score = retarget_component_breakdown(item["component_breakdown"], target_demo)
    item["component_breakdown"] = components
    item["opportunity_score"] = score
    item["calculation_method"] = (
        f"{item['calculation_method']} Retargeted target_demo={target_demo}."
    )
    return item


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
        "freshness_at": row["calculated_at"].isoformat(),
        "freshness_age_hours": age_hours(row["calculated_at"]),
    }


def _proximity_item(
    row: dict[str, Any],
    *,
    radius_km: float,
    near_category: str,
) -> dict[str, Any]:
    nearby = list(row.get("nearby_operators") or [])
    min_distance = (
        float(row["min_distance_km"]) if row.get("min_distance_km") is not None else None
    )
    proximity_score = (
        round(max(0.0, 1 - (min_distance / radius_km)), 4)
        if min_distance is not None and radius_km > 0
        else 0.0
    )
    source_refs = _unique_refs(
        [
            *list(row["source_refs"] or []),
            *[
                ref
                for operator in nearby
                for ref in operator.get("source_refs", [])
                if isinstance(ref, dict)
            ],
        ]
    )
    return {
        "operator_id": row["id"],
        "name": row["name"],
        "categories": row["categories"],
        "municipality": row["municipality"],
        "neighborhood": row["neighborhood"],
        "lat": float(row["lat"]),
        "lng": float(row["lng"]),
        "near_category": near_category,
        "nearby_count": int(row["nearby_count"] or 0),
        "min_distance_km": round(min_distance, 3) if min_distance is not None else None,
        "radius_km": radius_km,
        "proximity_score": proximity_score,
        "nearby_operators": nearby,
        "source_refs": source_refs,
        "confidence_score": float(row["confidence_score"]),
    }


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
