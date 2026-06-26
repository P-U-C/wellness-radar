from __future__ import annotations

import csv
import io
import json
import time
from typing import Any, Literal, cast

from fastapi import APIRouter, HTTPException, Query, Request, Response

from apps.api.app.db.bounds import parse_bbox
from apps.api.app.db.connection import get_connection
from apps.api.app.services.freshness import age_hours, iso_or_none
from apps.api.app.services.metrics import runtime_metrics

router = APIRouter(tags=["operators"])
MAX_OPERATOR_LIMIT = 5000
MAX_LEADS_LIMIT = 500
VenueClassFilter = Literal["commercial_wellness", "public_recreation", "unknown", "all"]
VENUE_CLASS_QUERY = Query(default="all")
DEDUPED_OPERATOR_CLAUSE = """
NOT EXISTS (
  SELECT 1
  FROM "operator" dupe
  WHERE dupe.id <> op.id
    AND dupe.geom IS NOT NULL
    AND jsonb_array_length(dupe.source_refs) > 0
    AND dupe.normalized_name = op.normalized_name
    AND (
      (
        NULLIF(regexp_replace(lower(COALESCE(dupe.address, '')), '[^a-z0-9]+', ' ', 'g'), '')
        =
        NULLIF(regexp_replace(lower(COALESCE(op.address, '')), '[^a-z0-9]+', ' ', 'g'), '')
      )
      OR ST_DWithin(dupe.geom, op.geom, 150)
    )
    AND (
      dupe.confidence_score > op.confidence_score
      OR (
        dupe.confidence_score = op.confidence_score
        AND dupe.last_seen_at > op.last_seen_at
      )
      OR (
        dupe.confidence_score = op.confidence_score
        AND dupe.last_seen_at = op.last_seen_at
        AND dupe.id < op.id
      )
    )
)
"""


def _operator_row(row: dict[str, Any]) -> dict[str, Any]:
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
        "neighborhood_assignment_method": row.get("neighborhood_assignment_method"),
        "neighborhood_assignment_source": row.get("neighborhood_assignment_source"),
        "neighborhood_assignment_confidence": (
            float(row["neighborhood_assignment_confidence"])
            if row.get("neighborhood_assignment_confidence") is not None
            else None
        ),
        "confidence_score": float(row["confidence_score"]),
        "source_refs": row["source_refs"],
        "freshness_at": iso_or_none(row.get("last_seen_at")),
        "freshness_age_hours": age_hours(row.get("last_seen_at")),
    }


@router.get("/operators")
def list_operators(
    bbox: str | None = Query(default=None),
    category: str | None = Query(default=None),
    venue_class: VenueClassFilter = VENUE_CLASS_QUERY,
    status: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1),
) -> dict[str, Any]:
    active_limit = min(limit, MAX_OPERATOR_LIMIT)
    try:
        parsed_bbox = parse_bbox(bbox)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    clauses = [
        "op.geom IS NOT NULL",
        "jsonb_array_length(op.source_refs) > 0",
        """
        ST_Intersects(
          op.geom,
          ST_MakeEnvelope(%s, %s, %s, %s, 4326)::geography
        )
        """,
        DEDUPED_OPERATOR_CLAUSE,
    ]
    params: list[Any] = [*parsed_bbox]
    if category:
        clauses.append("%s = ANY(op.categories)")
        params.append(category)
    if venue_class != "all":
        clauses.append("op.venue_class = %s")
        params.append(venue_class)
    if status:
        clauses.append("op.status = %s::operator_status")
        params.append(status)
    where_sql = " AND ".join(clauses)

    sql = f"""
      SELECT
        op.id,
        op.name,
        op.categories,
        op.venue_class,
        op.status::text AS status,
        op.address,
        op.municipality,
        COALESCE(NULLIF(op.neighborhood, ''), derived_neighborhood.geo_name) AS neighborhood,
        op.phone,
        op.website,
        op.social_links,
        op.organization_id,
        op.orgbook_id,
        op.neighborhood_assignment_method,
        op.neighborhood_assignment_source,
        op.neighborhood_assignment_confidence,
        ST_Y(op.geom::geometry) AS lat,
        ST_X(op.geom::geometry) AS lng,
        op.confidence_score,
        op.source_refs,
        op.last_seen_at,
        contacts.contacts
      FROM "operator" op
      LEFT JOIN LATERAL ({_derived_neighborhood_lateral_sql()}) derived_neighborhood ON TRUE
      LEFT JOIN LATERAL ({_contacts_lateral_sql()}) contacts ON TRUE
      WHERE {where_sql}
      ORDER BY op.last_seen_at DESC, op.name ASC
      LIMIT %s
    """
    start = time.perf_counter()
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(sql, [*params, active_limit]).fetchall(),
        )
        coverage = cast(
            dict[str, Any],
            conn.execute(
                f"""
                SELECT
                  count(*)::int AS operator_count,
                  count(*) FILTER (
                    WHERE EXISTS (
                      SELECT 1 FROM operator_contact oc WHERE oc.operator_id = op.id
                    )
                  )::int AS with_contact_count,
                  count(DISTINCT NULLIF(op.municipality, ''))::int AS municipality_count
                FROM "operator" op
                WHERE {where_sql}
                """,
                params,
            ).fetchone(),
        )
        municipality_rows = cast(
            list[dict[str, Any]],
            conn.execute(
                f"""
                SELECT NULLIF(op.municipality, '') AS municipality, count(*)::int AS operator_count
                FROM "operator" op
                WHERE {where_sql} AND NULLIF(op.municipality, '') IS NOT NULL
                GROUP BY 1
                ORDER BY operator_count DESC, municipality ASC
                """,
                params,
            ).fetchall(),
        )
    runtime_metrics.observe_map_query(duration_ms=(time.perf_counter() - start) * 1000)
    items = [_operator_row(row) for row in rows]
    total = int(coverage["operator_count"] or 0)
    with_contact = int(coverage["with_contact_count"] or 0)
    municipalities = [
        {"name": str(row["municipality"]), "operator_count": int(row["operator_count"] or 0)}
        for row in municipality_rows
    ]
    return {
        "items": items,
        "meta": {
            "count": len(items),
            "bbox": parsed_bbox,
            "limit": active_limit,
            "requested_limit": limit,
            "max_limit": MAX_OPERATOR_LIMIT,
            "venue_class": venue_class,
            "contact_coverage": {
                "operator_count": total,
                "with_contact_count": with_contact,
                "coverage_ratio": round(with_contact / total, 4) if total else 0,
            },
            "municipality_coverage": {
                "municipality_count": int(coverage["municipality_count"] or 0),
                "municipalities": municipalities,
            },
        },
    }


@router.get("/operators/{operator_id}")
def get_operator(operator_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        row = cast(
            dict[str, Any] | None,
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
                  COALESCE(NULLIF(op.neighborhood, ''), derived_neighborhood.geo_name)
                    AS neighborhood,
                  op.phone,
                  op.website,
                  op.social_links,
                  op.organization_id,
                  op.orgbook_id,
                  op.neighborhood_assignment_method,
                  op.neighborhood_assignment_source,
                  op.neighborhood_assignment_confidence,
                  ST_Y(op.geom::geometry) AS lat,
                  ST_X(op.geom::geometry) AS lng,
                  op.confidence_score,
                  op.source_refs,
                  op.licence_ref,
                  op.first_seen_at,
                  op.last_seen_at,
                  contacts.contacts
                FROM "operator" op
                LEFT JOIN LATERAL ({_derived_neighborhood_lateral_sql()})
                  derived_neighborhood ON TRUE
                LEFT JOIN LATERAL ({_contacts_lateral_sql()}) contacts ON TRUE
                WHERE op.id = %s
                  AND op.geom IS NOT NULL
                  AND jsonb_array_length(op.source_refs) > 0
                """,
                (operator_id,),
            ).fetchone(),
        )
        if not row:
            raise HTTPException(status_code=404, detail="operator not found")
        signals = cast(
            list[dict[str, Any]],
            conn.execute(
                """
                SELECT
                  id,
                  type,
                  severity::text AS severity,
                  title,
                  summary,
                  why_it_matters,
                  source_name,
                  source_url,
                  trust_tier::text AS trust_tier,
                  occurred_at,
                  ST_Y(geom::geometry) AS lat,
                  ST_X(geom::geometry) AS lng,
                  related_operator_id,
                  confidence_score,
                  source_refs
                FROM signal
                WHERE related_operator_id = %s
                ORDER BY occurred_at DESC
                LIMIT 20
                """,
                (operator_id,),
            ).fetchall(),
        )

    item = _operator_row(row)
    item["licence_ref"] = row["licence_ref"]
    item["first_seen_at"] = row["first_seen_at"].isoformat()
    item["last_seen_at"] = row["last_seen_at"].isoformat()
    item["signals"] = [
        {
            **signal,
            "occurred_at": signal["occurred_at"].isoformat(),
            "lat": float(signal["lat"]) if signal["lat"] is not None else None,
            "lng": float(signal["lng"]) if signal["lng"] is not None else None,
            "confidence_score": float(signal["confidence_score"]),
        }
        for signal in signals
    ]
    return item


@router.get("/leads")
def list_leads(
    request: Request,
    category: str | None = Query(default=None),
    bundle: str | None = Query(default=None),
    municipality: str | None = Query(default=None),
    has_contact: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1),
    format: Literal["json", "csv"] = Query(default="json"),
) -> Any:
    active_limit = min(limit, MAX_LEADS_LIMIT)
    clauses = [
        "op.geom IS NOT NULL",
        "jsonb_array_length(op.source_refs) > 0",
        DEDUPED_OPERATOR_CLAUSE,
    ]
    params: list[Any] = []
    if category:
        clauses.append("%s = ANY(op.categories)")
        params.append(category)
    if bundle:
        clauses.append(
            """
            EXISTS (
              SELECT 1
              FROM bundle_operator_membership bom
              JOIN bundle b ON b.id = bom.bundle_id
              WHERE bom.operator_id = op.id
                AND (b.id = %s OR b.slug = %s)
                AND jsonb_array_length(bom.source_refs) > 0
                AND jsonb_array_length(b.source_refs) > 0
            )
            """
        )
        params.extend([bundle, bundle])
    if municipality:
        clauses.append("op.municipality ILIKE %s")
        params.append(municipality)
    if has_contact is True:
        clauses.append("EXISTS (SELECT 1 FROM operator_contact oc WHERE oc.operator_id = op.id)")
    elif has_contact is False:
        clauses.append(
            "NOT EXISTS (SELECT 1 FROM operator_contact oc WHERE oc.operator_id = op.id)"
        )
    where_sql = " AND ".join(clauses)
    with get_connection() as conn:
        rows = cast(
            list[dict[str, Any]],
            conn.execute(_lead_select_sql(where_sql), [*params, active_limit]).fetchall(),
        )
    resolved_category = category or _category_for_bundle(bundle)
    items = [_lead_row(row, requested_category=resolved_category) for row in rows]
    wants_csv = format == "csv" or "text/csv" in request.headers.get("accept", "")
    if wants_csv:
        return Response(
            content=_rows_to_csv(_lead_csv_rows(items)),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="leads.csv"'},
        )
    return {
        "items": items,
        "meta": {
            "count": len(rows),
            "category": category,
            "bundle": bundle,
            "has_contact": has_contact,
            "limit": active_limit,
            "requested_limit": limit,
            "max_limit": MAX_LEADS_LIMIT,
        },
    }


@router.get("/leads/{lead_id}")
def get_lead(lead_id: str) -> dict[str, Any]:
    clauses = [
        "op.id = %s",
        "op.geom IS NOT NULL",
        "jsonb_array_length(op.source_refs) > 0",
        DEDUPED_OPERATOR_CLAUSE,
    ]
    with get_connection() as conn:
        row = cast(
            dict[str, Any] | None,
            conn.execute(_lead_select_sql(" AND ".join(clauses), include_order=False), [lead_id, 1])
            .fetchone(),
        )
    if not row:
        raise HTTPException(status_code=404, detail="lead not found")
    return _lead_row(row)


def _lead_row(row: dict[str, Any], requested_category: str | None = None) -> dict[str, Any]:
    item = _operator_row(row)
    item["category"] = _lead_category(item["categories"], requested_category=requested_category)
    item["contact_count"] = int(row.get("contact_count") or 0)
    item["opportunity_context"] = {
        "signal_count": int(row.get("signal_count") or 0),
        "geo_name": row.get("opportunity_geo_name"),
        "opportunity_score": (
            float(row["opportunity_score"]) if row.get("opportunity_score") is not None else None
        ),
        "source_refs": row.get("opportunity_source_refs") or [],
    }
    return item


def _lead_select_sql(where_sql: str, *, include_order: bool = True) -> str:
    order_sql = (
        """
        ORDER BY
          contacts.contact_count DESC,
          opportunity.opportunity_score DESC NULLS LAST,
          op.name ASC
        """
        if include_order
        else ""
    )
    return f"""
      SELECT
        op.id,
        op.name,
        op.categories,
        op.venue_class,
        op.status::text AS status,
        op.address,
        op.municipality,
        COALESCE(NULLIF(op.neighborhood, ''), derived_neighborhood.geo_name)
          AS neighborhood,
        op.phone,
        op.website,
        op.social_links,
        op.organization_id,
        op.orgbook_id,
        op.neighborhood_assignment_method,
        op.neighborhood_assignment_source,
        op.neighborhood_assignment_confidence,
        ST_Y(op.geom::geometry) AS lat,
        ST_X(op.geom::geometry) AS lng,
        op.confidence_score,
        op.source_refs,
        op.last_seen_at,
        contacts.contacts,
        contacts.contact_count,
        COALESCE(signal_counts.signal_count, 0) AS signal_count,
        opportunity.geo_name AS opportunity_geo_name,
        opportunity.opportunity_score AS opportunity_score,
        opportunity.source_refs AS opportunity_source_refs
      FROM "operator" op
      LEFT JOIN LATERAL ({_derived_neighborhood_lateral_sql()})
        derived_neighborhood ON TRUE
      LEFT JOIN LATERAL ({_contacts_lateral_sql()}) contacts ON TRUE
      LEFT JOIN LATERAL (
        SELECT count(*)::int AS signal_count
        FROM signal s
        WHERE s.related_operator_id = op.id
          AND jsonb_array_length(s.source_refs) > 0
      ) signal_counts ON TRUE
      LEFT JOIN LATERAL (
        SELECT os.geo_name, os.opportunity_score, os.source_refs
        FROM opportunity_scorecard os
        WHERE os.category = op.categories[1]
          AND jsonb_array_length(os.source_refs) > 0
          AND (
            lower(os.geo_name) = lower(COALESCE(op.municipality, ''))
            OR lower(os.geo_name) = lower(
              COALESCE(NULLIF(op.neighborhood, ''), derived_neighborhood.geo_name, '')
            )
            OR lower(os.geo_name) LIKE (
              '%%' || lower(COALESCE(op.municipality, '')) || '%%'
            )
          )
        ORDER BY os.opportunity_score DESC
        LIMIT 1
      ) opportunity ON TRUE
      WHERE {where_sql}
      {order_sql}
      LIMIT %s
    """


def _lead_category(
    categories: list[str] | tuple[str, ...], *, requested_category: str | None = None
) -> str | None:
    if requested_category and requested_category in categories:
        return requested_category
    return categories[0] if categories else None


def _category_for_bundle(bundle: str | None) -> str | None:
    if not bundle:
        return None
    normalized = bundle.removeprefix("bundle_").replace("-", "_")
    bundle_categories = {
        "cold_plunge_contrast_therapy": "recovery_contrast_therapy",
        "spa_thermal": "spa_thermal",
        "boutique_strength": "fitness_movement",
        "pickleball_court_sports": "racquet_court_sports",
        "climbing_bouldering": "climbing",
        "combat_martial_arts": "combat_sports",
        "public_recreation_courts_fields": "public_recreation",
        "aquatics_ice_rinks": "aquatics",
        "yoga_pilates": "fitness_movement",
        "longevity_iv": "nutrition_longevity",
        "allied_health_bodywork": "allied_health",
        "social_wellness_clubs": "community_social_wellness",
        "mind_breathwork": "mind_meditation",
        "wellness_retail": "wellness_retail_product",
    }
    return bundle_categories.get(normalized)


def _contacts_lateral_sql() -> str:
    return """
      SELECT
        COALESCE(
          jsonb_agg(
            jsonb_build_object(
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
        ) AS contacts,
        count(oc.id)::int AS contact_count
      FROM operator_contact oc
      WHERE oc.operator_id = op.id
    """


def _derived_neighborhood_lateral_sql() -> str:
    return """
      SELECT geo.geo_name
      FROM statcan_geography geo
      LEFT JOIN statcan_geography parent ON parent.geo_code = geo.parent_geo_code
      WHERE geo.geo_level = 'neighborhood'
        AND geo.geom IS NOT NULL
        AND op.geom IS NOT NULL
        AND (
          op.neighborhood IS NULL
          OR trim(op.neighborhood) = ''
        )
        AND (
          op.municipality IS NULL
          OR parent.geo_name IS NULL
          OR lower(parent.geo_name) = lower(op.municipality)
        )
      ORDER BY ST_Distance(op.geom, geo.geom) ASC
      LIMIT 1
    """


def _lead_csv_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        contacts = item.get("contacts") or [None]
        for contact in contacts:
            source_ref = contact.get("source_ref") if isinstance(contact, dict) else {}
            rows.append(
                {
                    "operator_id": item["id"],
                    "operator_name": item["name"],
                    "categories": item["categories"],
                    "status": item["status"],
                    "address": item["address"],
                    "municipality": item["municipality"],
                    "neighborhood": item["neighborhood"],
                    "contact_type": (
                        contact.get("contact_type") or contact.get("type")
                        if isinstance(contact, dict)
                        else None
                    ),
                    "contact_value": contact.get("value") if isinstance(contact, dict) else None,
                    "contact_platform": (
                        contact.get("platform") if isinstance(contact, dict) else None
                    ),
                    "contact_confidence": (
                        contact.get("confidence") if isinstance(contact, dict) else None
                    ),
                    "contact_source_name": source_ref.get("source_name")
                    if isinstance(source_ref, dict)
                    else None,
                    "contact_source_url": source_ref.get("url")
                    if isinstance(source_ref, dict)
                    else None,
                    "contact_source_record_id": source_ref.get("source_record_id")
                    if isinstance(source_ref, dict)
                    else None,
                    "source_refs": item["source_refs"],
                    "opportunity_geo_name": item["opportunity_context"]["geo_name"],
                    "opportunity_score": item["opportunity_context"]["opportunity_score"],
                }
            )
    return rows


def _rows_to_csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    output = io.StringIO()
    fieldnames = [
        "operator_id",
        "operator_name",
        "categories",
        "status",
        "address",
        "municipality",
        "neighborhood",
        "contact_type",
        "contact_value",
        "contact_platform",
        "contact_confidence",
        "contact_source_name",
        "contact_source_url",
        "contact_source_record_id",
        "opportunity_geo_name",
        "opportunity_score",
        "source_refs",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _csv_value(row.get(key)) for key in fieldnames})
    return output.getvalue()


def _csv_value(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict | list):
        return json.dumps(value, sort_keys=True, default=str)
    return value
