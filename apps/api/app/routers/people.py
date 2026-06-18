from __future__ import annotations

from typing import Any, Literal, cast

from fastapi import APIRouter, HTTPException, Query

from apps.api.app.db.connection import get_connection

router = APIRouter(tags=["people"])


@router.get("/people")
def list_people(
    sort: Literal["confidence", "name", "role"] = Query(default="confidence"),
    limit: int = Query(default=100, ge=1, le=250),
) -> dict[str, Any]:
    order_by = {
        "confidence": "confidence_score DESC, name ASC",
        "name": "name ASC",
        "role": "roles[1] ASC NULLS LAST, confidence_score DESC",
    }[sort]
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(
                f"""
                SELECT
                  id,
                  name,
                  roles,
                  affiliations,
                  public_profiles,
                  influence_score,
                  locality_score,
                  confidence_score,
                  source_refs
                FROM person
                ORDER BY {order_by}
                LIMIT %s
                """,
                (limit,),
            ).fetchall(),
        )
    return {"items": [_person_item(row) for row in rows], "meta": {"count": len(rows)}}


@router.get("/people/{person_id}")
def get_person(person_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        row = cast(
            dict[str, Any] | None,
            conn.execute(
                """
                SELECT
                  id,
                  name,
                  roles,
                  affiliations,
                  public_profiles,
                  influence_score,
                  locality_score,
                  confidence_score,
                  source_refs
                FROM person
                WHERE id = %s
                """,
                (person_id,),
            ).fetchone(),
        )
    if not row:
        raise HTTPException(status_code=404, detail="person not found")
    return _person_item(row)


def _person_item(row: dict[str, Any]) -> dict[str, Any]:
    affiliation = row["affiliations"][0] if row["affiliations"] else {}
    return {
        "id": row["id"],
        "name": row["name"],
        "roles": row["roles"],
        "primary_role": row["roles"][0] if row["roles"] else None,
        "primary_affiliation": affiliation.get("organization_name"),
        "affiliation_role": affiliation.get("role"),
        "public_profiles": row["public_profiles"],
        "influence_score": row["influence_score"],
        "locality_score": row["locality_score"],
        "confidence_score": float(row["confidence_score"]),
        "source_refs": row["source_refs"],
    }
