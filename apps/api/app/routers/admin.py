from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Query

from apps.api.app.db.connection import get_connection

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/source-runs")
def source_runs(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(
            """
            SELECT
              id,
              source_name,
              status::text AS status,
              started_at,
              completed_at,
              records_fetched,
              records_persisted,
              records_rejected,
              error_count,
              error_message
            FROM source_run
            ORDER BY started_at DESC
            LIMIT %s
            """,
            (limit,),
            ).fetchall(),
        )
    return {
        "items": [
            {
                **row,
                "started_at": row["started_at"].isoformat(),
                "completed_at": row["completed_at"].isoformat()
                if row["completed_at"] is not None
                else None,
            }
            for row in rows
        ],
        "meta": {"count": len(rows)},
    }


@router.get("/rejected-records")
def rejected_records(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(
            """
            SELECT id, source_name, reason, raw_payload_id, raw, rejected_at
            FROM rejected_record
            ORDER BY rejected_at DESC
            LIMIT %s
            """,
            (limit,),
            ).fetchall(),
        )
    return {
        "items": [
            {**row, "rejected_at": row["rejected_at"].isoformat()}
            for row in rows
        ],
        "meta": {"count": len(rows)},
    }


@router.get("/source-registry")
def source_registry() -> dict[str, Any]:
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(
            """
            SELECT
              source_name,
              family,
              base_url,
              cadence,
              licence,
              cost,
              trust_tier::text AS trust_tier,
              geo_rule,
              phase,
              rights_notes,
              enabled,
              updated_at
            FROM source_registry
            ORDER BY phase ASC, source_name ASC
            """
            ).fetchall(),
        )
    return {
        "items": [
            {**row, "updated_at": row["updated_at"].isoformat()}
            for row in rows
        ],
        "meta": {"count": len(rows)},
    }
