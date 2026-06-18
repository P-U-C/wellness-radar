from __future__ import annotations

from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from apps.api.app.db.connection import get_connection
from apps.api.app.security import Principal, require_permission
from apps.api.app.services.audit import audit_api_action
from apps.api.app.services.freshness import age_hours, iso_or_none
from packages.shared.ids import stable_id

router = APIRouter(tags=["people"])
CorrectionWritePrincipal = Annotated[Principal, Depends(require_permission("correction:write"))]


class PeopleCorrectionRequest(BaseModel):
    requester_name: str | None = None
    requester_email: str | None = None
    correction_summary: str = Field(min_length=10, max_length=4000)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)


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
                  p.last_seen_at,
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
                  p.last_seen_at,
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


@router.post("/people/{person_id}/correction-requests", status_code=201)
def create_people_correction_request(
    person_id: str,
    payload: PeopleCorrectionRequest,
    request: Request,
    principal: CorrectionWritePrincipal,
) -> dict[str, Any]:
    correction_id = stable_id(
        "person_correction",
        person_id,
        payload.requester_email or principal.actor_id,
        payload.correction_summary,
    )
    with get_connection() as conn:
        exists = conn.execute("SELECT 1 FROM person WHERE id = %s", (person_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="person not found")
        conn.execute(
            """
            INSERT INTO people_correction_request (
              id,
              person_id,
              requester_name,
              requester_email,
              correction_summary,
              source_refs,
              created_by_role
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                correction_id,
                person_id,
                payload.requester_name,
                payload.requester_email,
                payload.correction_summary,
                Jsonb(payload.source_refs),
                principal.role,
            ),
        )
        audit_api_action(
            conn,
            request=request,
            principal=principal,
            action="people_correction_requested",
            entity_type="person",
            entity_id=person_id,
            metadata={"correction_id": correction_id},
        )
    return {"id": correction_id, "status": "open", "person_id": person_id}


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
        "freshness_at": iso_or_none(row.get("last_seen_at")),
        "freshness_age_hours": age_hours(row.get("last_seen_at")),
    }
