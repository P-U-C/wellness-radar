from __future__ import annotations

import time
from typing import Any, cast

from fastapi import APIRouter, HTTPException, Query

from apps.api.app.db.bounds import parse_bbox
from apps.api.app.db.connection import get_connection
from apps.api.app.services.freshness import age_hours, iso_or_none
from apps.api.app.services.metrics import runtime_metrics

router = APIRouter(tags=["operators"])


def _operator_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "categories": row["categories"],
        "status": row["status"],
        "address": row["address"],
        "municipality": row["municipality"],
        "neighborhood": row["neighborhood"],
        "lat": float(row["lat"]),
        "lng": float(row["lng"]),
        "organization_id": row.get("organization_id"),
        "orgbook_id": row.get("orgbook_id"),
        "confidence_score": float(row["confidence_score"]),
        "source_refs": row["source_refs"],
        "freshness_at": iso_or_none(row.get("last_seen_at")),
        "freshness_age_hours": age_hours(row.get("last_seen_at")),
    }


@router.get("/operators")
def list_operators(
    bbox: str | None = Query(default=None),
    category: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=1000),
) -> dict[str, Any]:
    try:
        parsed_bbox = parse_bbox(bbox)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    clauses = [
        "geom IS NOT NULL",
        """
        ST_Intersects(
          geom,
          ST_MakeEnvelope(%s, %s, %s, %s, 4326)::geography
        )
        """,
    ]
    params: list[Any] = [*parsed_bbox]
    if category:
        clauses.append("%s = ANY(categories)")
        params.append(category)
    if status:
        clauses.append("status = %s::operator_status")
        params.append(status)
    params.append(limit)

    sql = f"""
      SELECT
        id,
        name,
        categories,
        status::text AS status,
        address,
        municipality,
        neighborhood,
        organization_id,
        orgbook_id,
        ST_Y(geom::geometry) AS lat,
        ST_X(geom::geometry) AS lng,
        confidence_score,
        source_refs,
        last_seen_at
      FROM "operator"
      WHERE {' AND '.join(clauses)}
      ORDER BY last_seen_at DESC, name ASC
      LIMIT %s
    """
    start = time.perf_counter()
    with get_connection() as conn:
        rows = cast(list[dict[str, Any]], conn.execute(sql, params).fetchall())
    runtime_metrics.observe_map_query(duration_ms=(time.perf_counter() - start) * 1000)
    items = [_operator_row(row) for row in rows]
    return {"items": items, "meta": {"count": len(items), "bbox": parsed_bbox}}


@router.get("/operators/{operator_id}")
def get_operator(operator_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        row = cast(
            dict[str, Any] | None,
            conn.execute(
            """
            SELECT
              id,
              name,
              categories,
              status::text AS status,
              address,
              municipality,
              neighborhood,
              organization_id,
              orgbook_id,
              ST_Y(geom::geometry) AS lat,
              ST_X(geom::geometry) AS lng,
              confidence_score,
              source_refs,
              licence_ref,
              first_seen_at,
              last_seen_at,
              payload
            FROM (
              SELECT op.*, '{}'::jsonb AS payload
              FROM "operator" op
            ) op
            WHERE id = %s AND geom IS NOT NULL
            """,
            (operator_id,),
            ).fetchone(),
        )
        if not row:
            raise HTTPException(status_code=404, detail="operator not found")
        signals = cast(
            list[dict[str, Any]],
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
              confidence_score,
              source_refs
            FROM signal
            WHERE related_operator_id = %s
            ORDER BY occurred_at DESC
            LIMIT 20
            """,
            (operator_id,),
            ).fetchall(),
        )

    item = _operator_row(row)
    item["licence_ref"] = row["licence_ref"]
    item["first_seen_at"] = row["first_seen_at"].isoformat()
    item["last_seen_at"] = row["last_seen_at"].isoformat()
    item["signals"] = [
        {
            **signal,
            "occurred_at": signal["occurred_at"].isoformat(),
            "lat": float(signal["lat"]) if signal["lat"] is not None else None,
            "lng": float(signal["lng"]) if signal["lng"] is not None else None,
            "confidence_score": float(signal["confidence_score"]),
        }
        for signal in signals
    ]
    return item
