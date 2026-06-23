from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal, cast

from fastapi import APIRouter, HTTPException, Query

from apps.api.app.db.connection import get_connection
from apps.api.app.services.freshness import age_hours, iso_or_none
from packages.schemas.api import BundleDetailResponse, BundlesResponse

router = APIRouter(tags=["bundles"])
MAX_BUNDLE_LIMIT = 100
BundleVenueClassFilter = Literal[
    "commercial_wellness", "public_recreation", "unknown", "all"
]
BUNDLE_VENUE_CLASS_QUERY = Query(default="commercial_wellness")


@router.get("/bundles", response_model=BundlesResponse)
def list_bundles(
    municipality: str | None = Query(default=None),
    geo_level: Literal["CSD", "neighborhood"] | None = Query(default=None),
    venue_class: BundleVenueClassFilter = BUNDLE_VENUE_CLASS_QUERY,
    limit: int = Query(default=50, ge=1),
) -> dict[str, Any]:
    active_limit = min(limit, MAX_BUNDLE_LIMIT)
    clauses = ["jsonb_array_length(b.source_refs) > 0"]
    params: list[Any] = []
    if municipality:
        clauses.append(
            """
            EXISTS (
              SELECT 1
              FROM jsonb_array_elements(
                COALESCE(b.geography->'municipalities', '[]'::jsonb)
              ) AS geo
              WHERE lower(geo->>'geo_name') = lower(%s)
                 OR lower(geo->>'municipality') = lower(%s)
            )
            """
        )
        params.extend([municipality, municipality])
    if geo_level:
        clauses.append(
            """
            EXISTS (
              SELECT 1
              FROM jsonb_array_elements(
                COALESCE(b.geography->'concentrations', '[]'::jsonb)
              ) AS geo
              WHERE geo->>'geo_level' = %s
            )
            """
        )
        params.append(geo_level)
    if venue_class != "all":
        clauses.append("b.venue_class = %s")
        params.append(venue_class)
    params.append(active_limit)
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(
                f"""
                SELECT
                  b.id,
                  b.label,
                  b.slug,
                  b.venue_class,
                  b.bundle_score,
                  b.components,
                  b.geography,
                  b.member_count,
                  b.supporting_signals,
                  b.source_refs,
                  b.confidence_score,
                  b.generated_at
                FROM bundle b
                WHERE {' AND '.join(clauses)}
                ORDER BY
                  CASE b.venue_class
                    WHEN 'commercial_wellness' THEN 0
                    WHEN 'public_recreation' THEN 1
                    ELSE 2
                  END,
                  b.bundle_score DESC,
                  b.label ASC
                LIMIT %s
                """,
                params,
            ).fetchall(),
        )
    return {
        "items": [_bundle_summary(row) for row in rows],
        "meta": {
            "count": len(rows),
            "limit": active_limit,
            "requested_limit": limit,
            "max_limit": MAX_BUNDLE_LIMIT,
            "municipality": municipality,
            "geo_level": geo_level,
            "venue_class": venue_class,
        },
    }


@router.get("/bundles/{bundle_id}", response_model=BundleDetailResponse)
def get_bundle(bundle_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        bundle = cast(
            dict[str, Any] | None,
            conn.execute(
                """
                SELECT
                  id,
                  label,
                  slug,
                  venue_class,
                  bundle_score,
                  components,
                  geography,
                  member_count,
                  supporting_signals,
                  source_refs,
                  confidence_score,
                  generated_at
                FROM bundle
                WHERE (id = %s OR slug = %s)
                  AND jsonb_array_length(source_refs) > 0
                """,
                (bundle_id, bundle_id),
            ).fetchone(),
        )
        if not bundle:
            raise HTTPException(status_code=404, detail="bundle not found")
        members = cast(
            list[dict[str, Any]],
            conn.execute(
                f"""
                SELECT
                  op.id,
                  op.name,
                  op.categories,
                  op.venue_class,
                  op.status::text AS status,
                  op.address,
                  op.municipality,
                  op.neighborhood,
                  op.phone,
                  op.website,
                  op.social_links,
                  op.organization_id,
                  op.orgbook_id,
                  ST_Y(op.geom::geometry) AS lat,
                  ST_X(op.geom::geometry) AS lng,
                  op.confidence_score,
                  op.source_refs,
                  op.last_seen_at,
                  bom.match_reasons,
                  bom.source_refs AS membership_source_refs,
                  bom.confidence_score AS membership_confidence_score,
                  contacts.contacts
                FROM bundle_operator_membership bom
                JOIN "operator" op ON op.id = bom.operator_id
                LEFT JOIN LATERAL ({_contacts_lateral_sql()}) contacts ON TRUE
                WHERE bom.bundle_id = %s
                  AND op.geom IS NOT NULL
                  AND jsonb_array_length(op.source_refs) > 0
                  AND jsonb_array_length(bom.source_refs) > 0
                ORDER BY bom.confidence_score DESC, op.name ASC
                """,
                (bundle["id"],),
            ).fetchall(),
        )
        people = cast(
            list[dict[str, Any]],
            conn.execute(
                """
                SELECT
                  bp.person_id AS id,
                  p.name,
                  p.roles,
                  p.affiliations,
                  p.public_profiles,
                  bp.rank,
                  bp.influence_score,
                  bp.why_appears,
                  bp.source_refs,
                  bp.confidence_score,
                  p.last_seen_at
                FROM bundle_person bp
                JOIN person p ON p.id = bp.person_id
                WHERE bp.bundle_id = %s
                  AND jsonb_array_length(bp.source_refs) > 0
                ORDER BY bp.rank ASC, p.name ASC
                """,
                (bundle["id"],),
            ).fetchall(),
        )
        worldwide_match = cast(
            dict[str, Any] | None,
            conn.execute(
                """
                SELECT worldwide_match, source_refs
                FROM bundle_global
                WHERE bundle_id = %s
                  AND jsonb_array_length(source_refs) > 0
                """,
                (bundle["id"],),
            ).fetchone(),
        )
        first_mover_cities = cast(
            list[dict[str, Any]],
            conn.execute(
                """
                SELECT
                  city,
                  count,
                  density,
                  ratio_vs_vancouver,
                  source_status,
                  source_refs,
                  confidence_score,
                  source_error
                FROM bundle_first_mover_city
                WHERE bundle_id = %s
                  AND jsonb_array_length(source_refs) > 0
                ORDER BY ratio_vs_vancouver DESC, density DESC, city ASC
                """,
                (bundle["id"],),
            ).fetchall(),
        )
    item = _bundle_summary(bundle)
    item["members"] = [_member_item(row) for row in members]
    item["top_people"] = [_person_item(row) for row in people]
    item["supporting_signals"] = bundle["supporting_signals"] or []
    item["worldwide_match"] = (
        _worldwide_match_item(worldwide_match) if worldwide_match else None
    )
    item["first_mover_cities"] = [_first_mover_city_item(row) for row in first_mover_cities]
    return item


def _bundle_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "label": row["label"],
        "slug": row["slug"],
        "venue_class": row["venue_class"],
        "bundle_score": float(row["bundle_score"]),
        "score": float(row["bundle_score"]),
        "components": row["components"],
        "geography": row["geography"],
        "member_count": row["member_count"],
        "supporting_signals": row["supporting_signals"] or [],
        "source_refs": row["source_refs"],
        "confidence_score": float(row["confidence_score"]),
        "generated_at": row["generated_at"].isoformat(),
        "freshness_at": row["generated_at"].isoformat(),
        "freshness_age_hours": age_hours(row["generated_at"]),
    }


def _member_item(row: dict[str, Any]) -> dict[str, Any]:
    source_refs = _unique_refs(
        [
            *list(row["membership_source_refs"] or []),
            *list(row["source_refs"] or []),
        ]
    )
    return {
        "id": row["id"],
        "name": row["name"],
        "categories": row["categories"],
        "venue_class": row["venue_class"],
        "status": row["status"],
        "address": row["address"],
        "municipality": row["municipality"],
        "neighborhood": row["neighborhood"],
        "lat": float(row["lat"]),
        "lng": float(row["lng"]),
        "phone": row.get("phone"),
        "website": row.get("website"),
        "social_links": row.get("social_links") or {},
        "contacts": row.get("contacts") or [],
        "organization_id": row.get("organization_id"),
        "orgbook_id": row.get("orgbook_id"),
        "match_reasons": row["match_reasons"],
        "membership_confidence_score": float(row["membership_confidence_score"]),
        "confidence_score": float(row["confidence_score"]),
        "source_refs": source_refs,
        "freshness_at": iso_or_none(row.get("last_seen_at")),
        "freshness_age_hours": age_hours(row.get("last_seen_at")),
    }


def _person_item(row: dict[str, Any]) -> dict[str, Any]:
    affiliations = row["affiliations"] or []
    primary_affiliation = affiliations[0].get("organization_name") if affiliations else None
    return {
        "id": row["id"],
        "name": row["name"],
        "roles": row["roles"],
        "primary_role": row["roles"][0] if row["roles"] else None,
        "primary_affiliation": primary_affiliation,
        "rank": row["rank"],
        "influence_score": (
            float(row["influence_score"]) if row["influence_score"] is not None else None
        ),
        "why_appears": row["why_appears"],
        "public_profiles": row["public_profiles"],
        "confidence_score": float(row["confidence_score"]),
        "source_refs": row["source_refs"],
        "freshness_at": iso_or_none(row.get("last_seen_at")),
        "freshness_age_hours": age_hours(row.get("last_seen_at")),
    }


def _worldwide_match_item(row: dict[str, Any]) -> dict[str, Any]:
    worldwide_match = dict(row["worldwide_match"] or {})
    source_refs = _unique_refs(
        [
            *list(worldwide_match.get("source_refs") or []),
            *list(row["source_refs"] or []),
        ]
    )
    worldwide_match["source_refs"] = source_refs
    if worldwide_match.get("value") is not None:
        worldwide_match["value"] = float(worldwide_match["value"])
    if worldwide_match.get("confidence_score") is not None:
        worldwide_match["confidence_score"] = float(worldwide_match["confidence_score"])
    return worldwide_match


def _first_mover_city_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "city": row["city"],
        "count": row["count"],
        "density": float(row["density"]),
        "ratio_vs_vancouver": float(row["ratio_vs_vancouver"]),
        "source_status": row["source_status"],
        "confidence_score": float(row["confidence_score"]),
        "source_error": row.get("source_error"),
        "source_refs": row["source_refs"],
    }


def _contacts_lateral_sql() -> str:
    return """
      SELECT COALESCE(
        jsonb_agg(
          jsonb_build_object(
            'id', oc.id,
            'type', oc.contact_type,
            'contact_type', oc.contact_type,
            'value', oc.value,
            'platform', oc.platform,
            'source_ref', oc.source_ref,
            'confidence', oc.confidence_score
          )
          ORDER BY oc.contact_type, oc.value
        ),
        '[]'::jsonb
      ) AS contacts
      FROM operator_contact oc
      WHERE oc.operator_id = op.id
    """


def _unique_refs(refs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for ref in refs:
        key = "|".join(str(ref.get(field)) for field in ("source_name", "url", "source_record_id"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(ref)
    return unique
