from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol, cast

from psycopg.types.json import Jsonb

from apps.jobs.runner import DatabaseRepository, RunMetrics
from packages.geo.bc_gate import CanonicalGeoRecord, GeoGateResult, bc_gate
from packages.schemas.canonical import SourceRef
from packages.shared.ids import stable_id

SOURCE_NAME = "city_vancouver_local_area_boundary"
DATASET_URL = "https://opendata.vancouver.ca/explore/dataset/local-area-boundary/"
API_URL = (
    "https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/"
    "local-area-boundary/records"
)
LICENCE = "Open Government Licence - Vancouver"


@dataclass(frozen=True)
class NeighborhoodBoundary:
    id: str
    municipality: str
    neighborhood: str
    geometry: dict[str, Any]
    centroid_lat: float
    centroid_lng: float
    source_refs: list[dict[str, Any]]
    confidence_score: float
    payload: dict[str, Any]


class NeighborhoodRepository(Protocol):
    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> Any:
        ...

    def ensure_source_rights(self, source_name: str) -> None:
        ...

    def create_source_run(self, source_name: str) -> int:
        ...

    def complete_source_run(
        self,
        run_id: int,
        *,
        status: str,
        records_fetched: int,
        records_persisted: int,
        records_rejected: int,
        error_count: int,
        error_message: str | None = None,
    ) -> None:
        ...

    def upsert_raw_payload(
        self, source_name: str, source_record_id: str, raw: dict[str, Any]
    ) -> str:
        ...

    def write_rejection(
        self,
        record: CanonicalGeoRecord,
        result: GeoGateResult,
        raw_payload_id: str,
    ) -> None:
        ...

    def upsert_boundary(self, boundary: NeighborhoodBoundary, gate: GeoGateResult) -> None:
        ...

    def mark_native_neighborhoods(self) -> int:
        ...

    def assign_point_in_polygon_neighborhoods(self) -> int:
        ...

    def assign_nearest_centroid_neighborhoods(self) -> int:
        ...

    def close(self) -> None:
        ...


class DatabaseNeighborhoodRepository(DatabaseRepository):
    def upsert_boundary(self, boundary: NeighborhoodBoundary, gate: GeoGateResult) -> None:
        self.conn.execute(
            """
            INSERT INTO neighborhood_boundary (
              id,
              source_name,
              municipality,
              neighborhood,
              geom,
              centroid,
              source_refs,
              confidence_score,
              bc_gate_result,
              payload
            )
            VALUES (
              %s,
              %s,
              %s,
              %s,
              ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))::geography,
              ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
              %s,
              %s,
              %s,
              %s
            )
            ON CONFLICT (source_name, municipality, neighborhood) DO UPDATE SET
              geom = EXCLUDED.geom,
              centroid = EXCLUDED.centroid,
              source_refs = EXCLUDED.source_refs,
              confidence_score = EXCLUDED.confidence_score,
              bc_gate_result = EXCLUDED.bc_gate_result,
              payload = EXCLUDED.payload,
              updated_at = now()
            """,
            (
                boundary.id,
                SOURCE_NAME,
                boundary.municipality,
                boundary.neighborhood,
                json.dumps(boundary.geometry),
                boundary.centroid_lng,
                boundary.centroid_lat,
                Jsonb(boundary.source_refs),
                boundary.confidence_score,
                Jsonb(
                    {
                        "passes": gate.passes,
                        "reason": gate.reason,
                        "confidence": gate.confidence,
                    }
                ),
                Jsonb(boundary.payload),
            ),
        )

    def mark_native_neighborhoods(self) -> int:
        cursor = self.conn.execute(
            """
            UPDATE "operator"
            SET
              neighborhood_assignment_method = COALESCE(
                neighborhood_assignment_method,
                'source_native'
              ),
              neighborhood_assignment_source = COALESCE(
                neighborhood_assignment_source,
                'operator_source'
              ),
              neighborhood_assignment_confidence = COALESCE(
                neighborhood_assignment_confidence,
                confidence_score
              ),
              neighborhood_assignment_updated_at = now()
            WHERE neighborhood IS NOT NULL
              AND trim(neighborhood) <> ''
              AND geom IS NOT NULL
              AND jsonb_array_length(source_refs) > 0
            """
        )
        return int(cursor.rowcount or 0)

    def assign_point_in_polygon_neighborhoods(self) -> int:
        cursor = self.conn.execute(
            """
            WITH candidate AS (
              SELECT
                op.id AS operator_id,
                boundary.neighborhood,
                boundary.source_name,
                boundary.source_refs,
                boundary.confidence_score,
                row_number() OVER (
                  PARTITION BY op.id
                  ORDER BY
                    CASE
                      WHEN lower(COALESCE(op.municipality, '')) = lower(boundary.municipality)
                      THEN 0 ELSE 1
                    END,
                    ST_Distance(op.geom, boundary.centroid)
                ) AS rank
              FROM "operator" op
              JOIN neighborhood_boundary boundary
                ON ST_Covers(boundary.geom::geometry, op.geom::geometry)
                -- Only assign a neighborhood from the operator's OWN municipality.
                -- Otherwise a border point gets a neighbouring city's local-area name
                -- (e.g. a Richmond operator labelled "Marpole"), poisoning gap scores.
                AND lower(COALESCE(op.municipality, '')) = lower(boundary.municipality)
              WHERE op.geom IS NOT NULL
                AND jsonb_array_length(op.source_refs) > 0
                AND (op.neighborhood IS NULL OR trim(op.neighborhood) = '')
            ),
            picked AS (
              SELECT * FROM candidate WHERE rank = 1
            )
            UPDATE "operator" op
            SET
              neighborhood = picked.neighborhood,
              neighborhood_assignment_method = 'point_in_polygon',
              neighborhood_assignment_source = picked.source_name,
              neighborhood_assignment_confidence = LEAST(
                1,
                GREATEST(op.confidence_score, picked.confidence_score)
              ),
              neighborhood_assignment_updated_at = now(),
              source_refs = (
                SELECT COALESCE(jsonb_agg(DISTINCT value), '[]'::jsonb)
                FROM jsonb_array_elements(op.source_refs || picked.source_refs) AS value
              )
            FROM picked
            WHERE op.id = picked.operator_id
            """
        )
        return int(cursor.rowcount or 0)

    def assign_nearest_centroid_neighborhoods(self) -> int:
        cursor = self.conn.execute(
            """
            WITH native_centroid AS (
              SELECT
                municipality,
                neighborhood,
                ST_Centroid(ST_Collect(geom::geometry))::geography AS centroid,
                'operator_neighborhood_centroid'::text AS source_name,
                '[]'::jsonb AS source_refs,
                0.64::real AS confidence_score
              FROM "operator"
              WHERE neighborhood IS NOT NULL
                AND trim(neighborhood) <> ''
                AND geom IS NOT NULL
                AND jsonb_array_length(source_refs) > 0
              GROUP BY municipality, neighborhood
            ),
            all_centroid AS (
              SELECT
                municipality,
                neighborhood,
                centroid,
                source_name,
                source_refs,
                confidence_score
              FROM neighborhood_boundary
              UNION ALL
              SELECT
                municipality,
                neighborhood,
                centroid,
                source_name,
                source_refs,
                confidence_score
              FROM native_centroid
            ),
            candidate AS (
              SELECT
                op.id AS operator_id,
                centroid.neighborhood,
                centroid.source_name,
                centroid.source_refs,
                centroid.confidence_score,
                ST_Distance(op.geom, centroid.centroid) AS distance_m,
                row_number() OVER (
                  PARTITION BY op.id
                  ORDER BY
                    CASE
                      WHEN lower(COALESCE(op.municipality, '')) =
                           lower(COALESCE(centroid.municipality, ''))
                      THEN 0 ELSE 1
                    END,
                    ST_Distance(op.geom, centroid.centroid)
                ) AS rank
              FROM "operator" op
              JOIN all_centroid centroid ON TRUE
              WHERE op.geom IS NOT NULL
                AND jsonb_array_length(op.source_refs) > 0
                AND (op.neighborhood IS NULL OR trim(op.neighborhood) = '')
                -- Same-municipality only: never approximate an operator into a
                -- different city's neighborhood (e.g. Surrey -> Central Port Coquitlam).
                AND lower(COALESCE(op.municipality, '')) = lower(COALESCE(centroid.municipality, ''))
            ),
            picked AS (
              SELECT * FROM candidate WHERE rank = 1
            )
            UPDATE "operator" op
            SET
              neighborhood = picked.neighborhood,
              neighborhood_assignment_method = 'nearest_centroid_approximate',
              neighborhood_assignment_source = picked.source_name,
              neighborhood_assignment_confidence = LEAST(
                0.72,
                GREATEST(0.45, picked.confidence_score)
              ),
              neighborhood_assignment_updated_at = now(),
              source_refs = CASE
                WHEN jsonb_array_length(picked.source_refs) = 0 THEN op.source_refs
                ELSE (
                  SELECT COALESCE(jsonb_agg(DISTINCT value), '[]'::jsonb)
                  FROM jsonb_array_elements(op.source_refs || picked.source_refs) AS value
                )
              END
            FROM picked
            WHERE op.id = picked.operator_id
            """
        )
        return int(cursor.rowcount or 0)


def run_neighborhood_assignment(
    repository: NeighborhoodRepository | None = None,
    *,
    client: Any | None = None,
) -> RunMetrics:
    repo = repository or DatabaseNeighborhoodRepository()
    metrics = RunMetrics()
    run_id = 0
    try:
        repo.ensure_source_rights(SOURCE_NAME)
        run_id = repo.create_source_run(SOURCE_NAME)
        raw_records = _fetch_boundary_records(client=client)
        metrics.records_fetched = len(raw_records)
        for raw in raw_records:
            boundary = _normalize_boundary(raw)
            raw_payload_id = repo.upsert_raw_payload(SOURCE_NAME, boundary.id, raw)
            gate_record = CanonicalGeoRecord(
                source_name=SOURCE_NAME,
                title=boundary.neighborhood,
                address=None,
                municipality=boundary.municipality,
                province="BC",
                country="CA",
                lat=boundary.centroid_lat,
                lng=boundary.centroid_lng,
                text=f"{boundary.neighborhood}, {boundary.municipality}, BC",
                statcan_geo_code=None,
                raw=raw,
            )
            gate = bc_gate(gate_record, repo)
            if not gate.passes:
                repo.write_rejection(gate_record, gate, raw_payload_id)
                metrics.records_rejected += 1
                continue
            repo.upsert_boundary(boundary, gate)
            metrics.records_persisted += 1
        native_count = repo.mark_native_neighborhoods()
        pip_count = repo.assign_point_in_polygon_neighborhoods()
        approximate_count = repo.assign_nearest_centroid_neighborhoods()
        metrics.records_persisted += native_count + pip_count + approximate_count
        repo.complete_source_run(
            run_id,
            status="success" if metrics.error_count == 0 else "partial",
            records_fetched=metrics.records_fetched,
            records_persisted=metrics.records_persisted,
            records_rejected=metrics.records_rejected,
            error_count=metrics.error_count,
            error_message=metrics.error_message,
        )
        return metrics
    except Exception as exc:
        metrics.error_count += 1
        metrics.error_message = str(exc)
        if run_id:
            repo.complete_source_run(
                run_id,
                status="failed",
                records_fetched=metrics.records_fetched,
                records_persisted=metrics.records_persisted,
                records_rejected=metrics.records_rejected,
                error_count=metrics.error_count,
                error_message=metrics.error_message,
            )
        raise
    finally:
        repo.close()


def _fetch_boundary_records(client: Any | None = None) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"limit": 100})
    url = f"{API_URL}?{params}"
    if client is not None and hasattr(client, "get_json"):
        payload = client.get_json(url)
    else:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "wellness-radar/0.1",
                "Accept": "application/json,*/*",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            raise RuntimeError(f"Vancouver boundary HTTP {exc.code}: {body[:240]}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("City Vancouver local-area boundary API returned a non-object payload")
    results = payload.get("results")
    if not isinstance(results, list):
        raise RuntimeError("City Vancouver local-area boundary API missing results array")
    return cast(list[dict[str, Any]], results)


def _normalize_boundary(raw: dict[str, Any]) -> NeighborhoodBoundary:
    name = str(raw.get("name") or "").strip()
    geom_feature = raw.get("geom") or {}
    geometry = geom_feature.get("geometry") if isinstance(geom_feature, dict) else None
    centroid = raw.get("geo_point_2d") or {}
    if not name or not isinstance(geometry, dict):
        raise RuntimeError("City Vancouver local-area boundary record missing name or geometry")
    lat = float(centroid["lat"])
    lng = float(centroid["lon"])
    seen_at = _utc_seen_at()
    source_refs = [
        SourceRef(
            source_name=SOURCE_NAME,
            url=DATASET_URL,
            trust_tier="official",
            seen_at=seen_at,
            source_record_id=name,
            licence=LICENCE,
        ).as_dict()
    ]
    return NeighborhoodBoundary(
        id=stable_id("nh_boundary", SOURCE_NAME, "Vancouver", name),
        municipality="Vancouver",
        neighborhood=name,
        geometry=geometry,
        centroid_lat=lat,
        centroid_lng=lng,
        source_refs=source_refs,
        confidence_score=0.94,
        payload={
            "dataset": "local-area-boundary",
            "assignment_note": (
                "Point-in-polygon assignments use City of Vancouver local-area "
                "boundaries. Nearest-centroid assignments are approximate and "
                "labeled on operator records."
            ),
        },
    )


def _utc_seen_at() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
