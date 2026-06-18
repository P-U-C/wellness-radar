from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Query

from apps.api.app.db.connection import get_connection

router = APIRouter(tags=["trends"])


@router.get("/trends")
def list_trends(
    term: str | None = Query(default=None),
    city: str | None = Query(default=None),
) -> dict[str, Any]:
    clauses = ["jsonb_array_length(source_refs) > 0"]
    params: list[Any] = []
    if term:
        clauses.append("term = %s")
        params.append(term)
    if city:
        clauses.append("city = %s")
        params.append(city)
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(
                f"""
                SELECT
                  term,
                  city,
                  geography_code,
                  growth_class,
                  series,
                  source_name,
                  fetched_at,
                  source_refs,
                  confidence_score,
                  is_stub,
                  methodology
                FROM trend
                WHERE {' AND '.join(clauses)}
                ORDER BY term ASC, city ASC
                """,
                params,
            ).fetchall(),
        )
    return {"items": [_trend_item(row) for row in rows], "meta": {"count": len(rows)}}


def _trend_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "term": row["term"],
        "city": row["city"],
        "geography_code": row["geography_code"],
        "growth_class": row["growth_class"],
        "series": row["series"],
        "source_name": row["source_name"],
        "fetched_at": row["fetched_at"].isoformat(),
        "source_refs": row["source_refs"],
        "confidence_score": float(row["confidence_score"]),
        "is_stub": row["is_stub"],
        "methodology": row["methodology"],
    }
