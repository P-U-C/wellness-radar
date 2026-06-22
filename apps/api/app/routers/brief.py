from __future__ import annotations

from datetime import date
from typing import Any, cast

from fastapi import APIRouter, HTTPException

from apps.api.app.db.connection import get_connection
from apps.api.app.services.freshness import age_hours

router = APIRouter(prefix="/brief", tags=["brief"])


@router.get("")
def latest_brief() -> dict[str, Any]:
    with get_connection() as conn:
        row = cast(
            dict[str, Any] | None,
            conn.execute(
                """
                SELECT
                  id,
                  brief_date,
                  generated_at,
                  window_start,
                  window_end,
                  status,
                  brief_text,
                  sections,
                  top_actions,
                  counts,
                  source_refs,
                  narrative_model
                FROM daily_brief
                ORDER BY generated_at DESC
                LIMIT 1
                """
            ).fetchone(),
        )
    if not row:
        raise HTTPException(status_code=404, detail="daily brief not found")
    return _brief_row(row)


@router.get("/{brief_date}")
def brief_by_date(brief_date: date) -> dict[str, Any]:
    with get_connection() as conn:
        row = cast(
            dict[str, Any] | None,
            conn.execute(
                """
                SELECT
                  id,
                  brief_date,
                  generated_at,
                  window_start,
                  window_end,
                  status,
                  brief_text,
                  sections,
                  top_actions,
                  counts,
                  source_refs,
                  narrative_model
                FROM daily_brief
                WHERE brief_date = %s
                """,
                (brief_date,),
            ).fetchone(),
        )
    if not row:
        raise HTTPException(status_code=404, detail="daily brief not found")
    return _brief_row(row)


def _brief_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "brief_date": row["brief_date"].isoformat(),
        "generated_at": row["generated_at"].isoformat(),
        "window_start": row["window_start"].isoformat(),
        "window_end": row["window_end"].isoformat(),
        "status": row["status"],
        "brief_text": row["brief_text"],
        "sections": row["sections"],
        "top_actions": row["top_actions"],
        "counts": row["counts"],
        "source_refs": row["source_refs"],
        "narrative_model": row["narrative_model"],
        "freshness_at": row["generated_at"].isoformat(),
        "freshness_age_hours": age_hours(row["generated_at"]),
    }
