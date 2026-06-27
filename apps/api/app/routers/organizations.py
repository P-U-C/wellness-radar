from __future__ import annotations

from typing import Any, Literal, cast

from fastapi import APIRouter, Query, Request

from apps.api.app.db.connection import get_connection
from apps.api.app.services.freshness import age_hours, iso_or_none

router = APIRouter(tags=["organizations"])
MAX_ORGANIZATION_LIMIT = 500


@router.get("/organizations")
@router.get("/employers")
def list_organizations(
    request: Request,
    orgbook_only: bool = Query(default=True),
    role: Literal["organization", "employer", "partner"] | None = Query(default=None),
    limit: int = Query(default=100, ge=1),
) -> dict[str, Any]:
    active_limit = min(limit, MAX_ORGANIZATION_LIMIT)
    resolved_role = role or (
        "employer" if request.url.path.rstrip("/").endswith("/employers") else "organization"
    )
    clauses = ["jsonb_array_length(org.source_refs) > 0"]
    params: list[Any] = []
    if orgbook_only:
        clauses.append("org.orgbook_id IS NOT NULL")
    params.append(active_limit)
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(
                f"""
                SELECT
                  org.id,
                  org.name,
                  org.registry_id,
                  org.orgbook_id,
                  org.organization_type,
                  org.website,
                  org.source_refs,
                  org.confidence_score,
                  org.last_seen_at,
                  location.location,
                  firmographics.headcount,
                  firmographics.industry,
                  firmographics.industry_code,
                  firmographics.source_refs AS firmographic_source_refs
                FROM organization org
                LEFT JOIN LATERAL (
                  SELECT jsonb_build_object(
                    'operator_id', op.id,
                    'operator_name', op.name,
                    'address', op.address,
                    'municipality', op.municipality,
                    'neighborhood', op.neighborhood,
                    'lat', ST_Y(op.geom::geometry),
                    'lng', ST_X(op.geom::geometry),
                    'source_refs', op.source_refs
                  ) AS location
                  FROM "operator" op
                  WHERE op.organization_id = org.id
                    AND jsonb_array_length(op.source_refs) > 0
                  ORDER BY op.confidence_score DESC, op.last_seen_at DESC
                  LIMIT 1
                ) location ON TRUE
                LEFT JOIN LATERAL (
                  SELECT
                    max(NULLIF(
                      regexp_replace(
                        COALESCE(
                          rp.raw_json->>'numberofemployees',
                          rp.raw_json->>'number_of_employees',
                          rp.raw_json->>'EMPLOYEES',
                          rp.raw_json->>'employees'
                        ),
                        '[^0-9]+',
                        '',
                        'g'
                      ),
                      ''
                    )::int) AS headcount,
                    max(NULLIF(COALESCE(
                      rp.raw_json->>'businesstype',
                      rp.raw_json->>'business_type',
                      rp.raw_json->>'BUSINESS_TYPE'
                    ), '')) AS industry,
                    max(NULLIF(COALESCE(
                      rp.raw_json->>'businesssubtype',
                      rp.raw_json->>'business_subtype',
                      rp.raw_json->>'TRADE_NAICS_CODE'
                    ), '')) AS industry_code,
                    COALESCE(jsonb_agg(DISTINCT ref), '[]'::jsonb) AS source_refs
                  FROM "operator" op
                  CROSS JOIN LATERAL jsonb_array_elements(op.source_refs) AS ref
                  JOIN raw_payload rp
                    ON rp.source_name = ref->>'source_name'
                   AND rp.source_record_id = ref->>'source_record_id'
                  WHERE op.organization_id = org.id
                    AND rp.raw_json IS NOT NULL
                ) firmographics ON TRUE
                WHERE {' AND '.join(clauses)}
                ORDER BY org.last_seen_at DESC, org.name ASC
                LIMIT %s
                """,
                params,
            ).fetchall(),
        )
    return {
        "items": [_organization_item(row, role=resolved_role) for row in rows],
        "meta": {
            "count": len(rows),
            "limit": active_limit,
            "requested_limit": limit,
            "max_limit": MAX_ORGANIZATION_LIMIT,
            "orgbook_only": orgbook_only,
            "role": resolved_role,
        },
    }


def _organization_item(row: dict[str, Any], *, role: str) -> dict[str, Any]:
    location = row.get("location") if isinstance(row.get("location"), dict) else None
    source_refs = _unique_refs(
        [
            *list(row["source_refs"] or []),
            *list(row.get("firmographic_source_refs") or []),
            *list((location or {}).get("source_refs") or []),
        ]
    )
    return {
        "id": row["id"],
        "role": role,
        "name": row["name"],
        "registry_id": row["registry_id"],
        "orgbook_id": row["orgbook_id"],
        "organization_type": row["organization_type"],
        "website": row["website"],
        "location": location,
        "headcount": int(row["headcount"]) if row.get("headcount") is not None else None,
        "industry": row.get("industry"),
        "industry_code": row.get("industry_code"),
        "source_refs": source_refs,
        "confidence_score": float(row["confidence_score"]),
        "freshness_at": iso_or_none(row.get("last_seen_at")),
        "freshness_age_hours": age_hours(row.get("last_seen_at")),
    }


def _unique_refs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        key = "|".join(str(ref.get(field)) for field in ("source_name", "url", "source_record_id"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(ref)
    return unique
