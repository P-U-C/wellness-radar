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
    live_rows = [row for row in rows if not row["is_stub"]]
    hidden_stub_count = len(rows) - len(live_rows)
    status = "live" if live_rows else "data_pending"
    pending_reason = None
    if not live_rows and hidden_stub_count:
        pending_reason = (
            "Fixture peer-city trend rows are hidden until a reviewed live trends "
            "provider is available."
        )
    elif not live_rows:
        pending_reason = "No reviewed live trend rows are available for this query."
    return {
        "items": [_trend_item(row) for row in live_rows],
        "meta": {
            "count": len(live_rows),
            "total_rows": len(rows),
            "hidden_stub_count": hidden_stub_count,
            "status": status,
            "pending_reason": pending_reason,
            "source_status_counts": {
                "live": len(live_rows),
                "stub_hidden": hidden_stub_count,
            },
        },
    }


def _trend_item(row: dict[str, Any]) -> dict[str, Any]:
    is_stub = bool(row["is_stub"])
    source_status = "data_pending" if is_stub else "live"
    return {
        "term": row["term"],
        "city": row["city"],
        "geography_code": row["geography_code"],
        "growth_class": "data_pending" if is_stub else row["growth_class"],
        "series": [] if is_stub else row["series"],
        "source_name": row["source_name"],
        "fetched_at": row["fetched_at"].isoformat(),
        "source_refs": row["source_refs"],
        "confidence_score": float(row["confidence_score"]),
        "is_stub": is_stub,
        "methodology": row["methodology"],
        "source_status": source_status,
        "status": source_status,
        "pending_reason": (
            "Illustrative fixture hidden from live demand views."
            if is_stub
            else None
        ),
    }
