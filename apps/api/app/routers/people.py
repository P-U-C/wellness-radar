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
MAX_PEOPLE_LIMIT = 250


class PeopleCorrectionRequest(BaseModel):
    requester_name: str | None = None
    requester_email: str | None = None
    correction_summary: str = Field(min_length=10, max_length=4000)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/people")
def list_people(
    sort: Literal["influence", "confidence", "name", "role"] = Query(default="influence"),
    category: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1),
) -> dict[str, Any]:
    active_limit = min(limit, MAX_PEOPLE_LIMIT)
    default_person_rank = """
      CASE
        WHEN person_categories.primary_category IS NOT NULL THEN 0
        WHEN lower(array_to_string(p.roles, ' ')) LIKE ANY (
          ARRAY['%%minister%%', '%%government%%', '%%provincial%%', '%%attorney general%%']
        )
          OR lower(p.affiliations::text) LIKE ANY (
            ARRAY['%%government of british columbia%%', '%%health authority%%']
          )
        THEN 2
        ELSE 1
      END
    """
    order_by = {
        "influence": (
            f"{default_person_rank} ASC, "
            "COALESCE(pic.influence_score, p.influence_score, 0) DESC, p.name ASC"
        ),
        "confidence": "p.confidence_score DESC, p.name ASC",
        "name": "p.name ASC",
        "role": "p.roles[1] ASC NULLS LAST, p.confidence_score DESC",
    }[sort]
    clauses = ["jsonb_array_length(p.source_refs) > 0"]
    params: list[Any] = []
    if category:
        clauses.append("%s = ANY(person_categories.categories)")
        params.append(category)
    params.append(active_limit)
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(
                _people_select_sql(" AND ".join(clauses), order_by=order_by),
                tuple(params),
            ).fetchall(),
        )
    return {
        "items": [_person_item(row) for row in rows],
        "meta": {
            "count": len(rows),
            "category": category,
            "limit": active_limit,
            "requested_limit": limit,
            "max_limit": MAX_PEOPLE_LIMIT,
        },
    }


@router.get("/people/{person_id}")
def get_person(person_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        row = cast(
            dict[str, Any] | None,
            conn.execute(
                _people_select_sql("p.id = %s AND jsonb_array_length(p.source_refs) > 0"),
                (person_id, 1),
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
    contacts = _public_person_contacts(row.get("public_profiles") or {})
    return {
        "id": row["id"],
        "name": row["name"],
        "roles": row["roles"],
        "primary_role": row["roles"][0] if row["roles"] else None,
        "primary_category": row.get("primary_category"),
        "categories": row.get("categories") or [],
        "primary_affiliation": affiliation.get("organization_name"),
        "affiliation_role": affiliation.get("role"),
        "public_profiles": row["public_profiles"],
        "contacts": contacts,
        "contactable": bool(contacts),
        "person_type": _person_type(row["roles"], row["affiliations"]),
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


def _people_select_sql(where_sql: str, *, order_by: str | None = None) -> str:
    order_sql = f"ORDER BY {order_by}" if order_by else ""
    return f"""
      SELECT
        p.id,
        p.name,
        p.roles,
        p.affiliations,
        p.public_profiles,
        person_categories.primary_category,
        person_categories.categories,
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
      LEFT JOIN LATERAL ({_person_category_lateral_sql()}) person_categories ON TRUE
      WHERE {where_sql}
      {order_sql}
      LIMIT %s
    """


def _person_category_lateral_sql() -> str:
    return """
      WITH affiliation_values AS (
        SELECT
          NULLIF(aff->>'operator_id', '') AS operator_id,
          NULLIF(lower(trim(aff->>'operator_name')), '') AS operator_name,
          NULLIF(lower(trim(aff->>'organization_name')), '') AS organization_name
        FROM jsonb_array_elements(p.affiliations) AS aff
      ),
      matched_ops AS (
        SELECT DISTINCT op.id, op.categories
        FROM "operator" op
        JOIN affiliation_values aff ON (
          (aff.operator_id IS NOT NULL AND op.id = aff.operator_id)
          OR (aff.operator_name IS NOT NULL AND lower(op.name) = aff.operator_name)
          OR (aff.organization_name IS NOT NULL AND lower(op.name) = aff.organization_name)
          OR (
            aff.organization_name IS NOT NULL
            AND length(aff.organization_name) >= 6
            AND lower(op.name) LIKE aff.organization_name || '%%'
          )
        )
        WHERE jsonb_array_length(op.source_refs) > 0
      ),
      category_rows AS (
        SELECT category, min(ordinality) AS first_position, count(*) AS match_count
        FROM matched_ops
        CROSS JOIN LATERAL unnest(matched_ops.categories)
          WITH ORDINALITY AS category_value(category, ordinality)
        GROUP BY category
      )
      SELECT
        (
          SELECT category
          FROM category_rows
          ORDER BY match_count DESC, first_position ASC, category ASC
          LIMIT 1
        ) AS primary_category,
        COALESCE(
          (
            SELECT array_agg(category ORDER BY match_count DESC, first_position ASC, category ASC)
            FROM category_rows
          ),
          ARRAY[]::text[]
        ) AS categories
    """


def _public_person_contacts(public_profiles: dict[str, Any]) -> list[dict[str, Any]]:
    contacts: list[dict[str, Any]] = []
    for key, contact_type in (("email", "email"), ("phone", "phone")):
        value = public_profiles.get(key)
        if not value:
            continue
        contacts.append(
            {
                "contact_type": contact_type,
                "type": contact_type,
                "value": value,
                "source": "public_profiles",
                "confidence": 0.6,
            }
        )
    return contacts


def _person_type(roles: list[str], affiliations: list[dict[str, Any]]) -> str:
    role_text = " ".join(roles).lower()
    affiliation_text = " ".join(
        str(item.get("organization_name") or "") for item in affiliations
    ).lower()
    if any(
        item.get("operator_id") or item.get("operator_name") for item in affiliations
    ):
        return "operator"
    if "operator" in role_text or any(
        key in affiliation_text for key in ("wellness", "aetherhaus", "tality")
    ):
        return "operator"
    if any(
        key in role_text or key in affiliation_text
        for key in ("minister", "government", "provincial", "advocate", "attorney")
    ):
        return "policy_figure"
    return "public_professional"
