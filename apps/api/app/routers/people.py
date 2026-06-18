from __future__ import annotations

from typing import Any, Literal, cast

from fastapi import APIRouter, HTTPException, Query

from apps.api.app.db.connection import get_connection

router = APIRouter(tags=["people"])


@router.get("/people")
def list_people(
    sort: Literal["influence", "confidence", "name", "role"] = Query(default="influence"),
    limit: int = Query(default=100, ge=1, le=250),
) -> dict[str, Any]:
    order_by = {
        "influence": "COALESCE(pic.influence_score, p.influence_score, 0) DESC, p.name ASC",
        "confidence": "p.confidence_score DESC, p.name ASC",
        "name": "p.name ASC",
        "role": "p.roles[1] ASC NULLS LAST, p.confidence_score DESC",
    }[sort]
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(
                f"""
                SELECT
                  p.id,
                  p.name,
                  p.roles,
                  p.affiliations,
                  p.public_profiles,
                  COALESCE(pic.influence_score, p.influence_score) AS influence_score,
                  p.locality_score,
                  p.confidence_score,
                  p.source_refs,
                  pic.component_breakdown AS influence_components,
                  pic.explanation AS influence_explanation,
                  pic.methodology_version AS influence_methodology_version,
                  pic.source_confidence AS influence_source_confidence,
                  pic.source_refs AS influence_source_refs
                FROM person p
                LEFT JOIN person_influence_component pic ON pic.person_id = p.id
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
                  p.id,
                  p.name,
                  p.roles,
                  p.affiliations,
                  p.public_profiles,
                  COALESCE(pic.influence_score, p.influence_score) AS influence_score,
                  p.locality_score,
                  p.confidence_score,
                  p.source_refs,
                  pic.component_breakdown AS influence_components,
                  pic.explanation AS influence_explanation,
                  pic.methodology_version AS influence_methodology_version,
                  pic.source_confidence AS influence_source_confidence,
                  pic.source_refs AS influence_source_refs
                FROM person p
                LEFT JOIN person_influence_component pic ON pic.person_id = p.id
                WHERE p.id = %s
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
        "influence_score": (
            float(row["influence_score"]) if row["influence_score"] is not None else None
        ),
        "locality_score": row["locality_score"],
        "confidence_score": float(row["confidence_score"]),
        "influence_components": row.get("influence_components"),
        "influence_explanation": row.get("influence_explanation"),
        "influence_methodology_version": row.get("influence_methodology_version"),
        "influence_source_confidence": (
            float(row["influence_source_confidence"])
            if row.get("influence_source_confidence") is not None
            else None
        ),
        "influence_source_refs": row.get("influence_source_refs") or [],
        "source_refs": row["source_refs"],
    }
