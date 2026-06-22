from __future__ import annotations

import time
from datetime import datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, HTTPException, Query

from apps.api.app.db.bounds import parse_bbox
from apps.api.app.db.connection import get_connection
from apps.api.app.services.freshness import age_hours, iso_or_none
from apps.api.app.services.metrics import runtime_metrics

router = APIRouter(tags=["signals"])
MAX_SIGNALS_LIMIT = 500


def _signal_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "type": row["type"],
        "severity": row["severity"],
        "title": row["title"],
        "summary": row["summary"],
        "why_it_matters": row["why_it_matters"],
        "source_name": row["source_name"],
        "source_url": row["source_url"],
        "trust_tier": row["trust_tier"],
        "occurred_at": row["occurred_at"].isoformat(),
        "lat": float(row["lat"]) if row["lat"] is not None else None,
        "lng": float(row["lng"]) if row["lng"] is not None else None,
        "related_operator_id": row["related_operator_id"],
        "related_organization_id": row["related_organization_id"],
        "confidence_score": float(row["confidence_score"]),
        "ai_generated_fields": row.get("ai_generated_fields", []),
        "prompt_version": row.get("prompt_version"),
        "ai_model": row.get("ai_model"),
        "ai_category_suggestions": row.get("ai_category_suggestions", []),
        "ai_severity_suggestion": row.get("ai_severity_suggestion"),
        "ai_confidence_score": float(row["ai_confidence_score"])
        if row.get("ai_confidence_score") is not None
        else None,
        "source_refs": row["source_refs"],
        "freshness_at": iso_or_none(row.get("ingested_at")),
        "freshness_age_hours": age_hours(row.get("ingested_at")),
    }


@router.get("/signals")
def list_signals(
    bbox: str | None = Query(default=None),
    type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    since: Annotated[datetime | None, Query()] = None,
    related_operator_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1),
) -> dict[str, Any]:
    active_limit = min(limit, MAX_SIGNALS_LIMIT)
    try:
        parsed_bbox = parse_bbox(bbox)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    clauses = [
        """
        (
          geom IS NULL
          OR ST_Intersects(
            geom,
            ST_MakeEnvelope(%s, %s, %s, %s, 4326)::geography
          )
        )
        """,
    ]
    params: list[Any] = [*parsed_bbox]
    if type:
        clauses.append("type = %s")
        params.append(type)
    if severity:
        clauses.append("severity = %s::signal_severity")
        params.append(severity)
    if since:
        clauses.append("occurred_at >= %s")
        params.append(since)
    if related_operator_id:
        clauses.append("related_operator_id = %s")
        params.append(related_operator_id)
    params.append(active_limit)

    sql = f"""
      SELECT
        id,
        type,
        severity::text AS severity,
        title,
        summary,
        why_it_matters,
        source_name,
        source_url,
        trust_tier::text AS trust_tier,
        occurred_at,
        ST_Y(geom::geometry) AS lat,
        ST_X(geom::geometry) AS lng,
        related_operator_id,
        related_organization_id,
        confidence_score,
        ai_generated_fields,
        prompt_version,
        ai_model,
        ai_category_suggestions,
        ai_severity_suggestion::text AS ai_severity_suggestion,
        ai_confidence_score,
        source_refs,
        ingested_at
      FROM signal
      WHERE {' AND '.join(clauses)}
      ORDER BY occurred_at DESC, ingested_at DESC
      LIMIT %s
    """
    start = time.perf_counter()
    with get_connection() as conn:
        rows = cast(list[dict[str, Any]], conn.execute(sql, params).fetchall())
    runtime_metrics.observe_map_query(duration_ms=(time.perf_counter() - start) * 1000)
    items = [_signal_item(row) for row in rows]
    return {
        "items": items,
        "meta": {
            "count": len(items),
            "bbox": parsed_bbox,
            "limit": active_limit,
            "requested_limit": limit,
            "max_limit": MAX_SIGNALS_LIMIT,
        },
    }


@router.get("/signals/{signal_id}")
def get_signal(signal_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        row = cast(
            dict[str, Any] | None,
            conn.execute(
            """
            SELECT
              id,
              type,
              severity::text AS severity,
              title,
              summary,
              why_it_matters,
              source_name,
              source_url,
              trust_tier::text AS trust_tier,
              occurred_at,
              ST_Y(geom::geometry) AS lat,
              ST_X(geom::geometry) AS lng,
              related_operator_id,
              related_organization_id,
              confidence_score,
              ai_generated_fields,
              prompt_version,
              ai_model,
              ai_category_suggestions,
              ai_severity_suggestion::text AS ai_severity_suggestion,
              ai_confidence_score,
              source_refs,
              ingested_at
            FROM signal
            WHERE id = %s
            """,
            (signal_id,),
            ).fetchone(),
        )
    if not row:
        raise HTTPException(status_code=404, detail="signal not found")
    return _signal_item(row)
