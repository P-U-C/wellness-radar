from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, cast

from psycopg.types.json import Jsonb

from apps.jobs.runner import DatabaseRepository, RunMetrics
from packages.geo.bc_gate import CanonicalGeoRecord, bc_gate
from packages.shared.ids import stable_id

OPPORTUNITY_METHOD = (
    "M3 v1: 0.30 demand_proxy + 0.20 low_supply_density + 0.15 category_growth "
    "+ 0.15 target_demo_fit + 0.10 transit_access + 0.05 event_community_activity "
    "+ 0.05 source_confidence. White-space means a supply-demand signal, not "
    "guaranteed economic attractiveness."
)
NEIGHBORHOOD_METHOD = (
    "CM3 neighborhood extension: supply is counted from BC-gated operators carrying "
    "neighborhood tags. Population and business denominators are allocated from the "
    "parent CSD when no official neighborhood denominator exists; raw parent values "
    "and allocation share are exposed in trace_payload."
)
DERIVED_NEIGHBORHOOD_SOURCE = "derived_neighborhood_analytics"
COMPETITOR_RADIUS_KM = 4.0


@dataclass(frozen=True)
class ScoreComponents:
    demand_proxy: float
    low_supply_density: float
    category_growth: float
    target_demo_fit: float
    transit_access: float
    event_community_activity: float
    source_confidence: float

    def score(self) -> float:
        return round(
            0.30 * self.demand_proxy
            + 0.20 * self.low_supply_density
            + 0.15 * self.category_growth
            + 0.15 * self.target_demo_fit
            + 0.10 * self.transit_access
            + 0.05 * self.event_community_activity
            + 0.05 * self.source_confidence,
            4,
        )

    def as_dict(self) -> dict[str, float]:
        return {
            "demand_proxy": self.demand_proxy,
            "low_supply_density": self.low_supply_density,
            "category_growth": self.category_growth,
            "target_demo_fit": self.target_demo_fit,
            "transit_access": self.transit_access,
            "event_community_activity": self.event_community_activity,
            "source_confidence": self.source_confidence,
        }


class OpportunityAnalyticsRepository(DatabaseRepository):
    def categories_with_denominators(self) -> list[str]:
        rows = self.conn.execute(
            """
            SELECT DISTINCT category
            FROM statcan_denominator
            WHERE metric = 'business_count'
              AND category IS NOT NULL
            ORDER BY category
            """
        ).fetchall()
        return [str(row["category"]) for row in rows]

    def geographies(self) -> list[dict[str, Any]]:
        return list(
            self.conn.execute(
                """
                SELECT
                  g.geo_code,
                  g.geo_level,
                  g.geo_name,
                  ST_Y(g.geom::geometry) AS lat,
                  ST_X(g.geom::geometry) AS lng,
                  g.source_refs AS geography_source_refs,
                  g.confidence_score AS geography_confidence,
                  g.payload AS geography_payload,
                  pop.id AS population_denominator_id,
                  pop.value AS population,
                  pop.source_refs AS population_source_refs,
                  pop.confidence_score AS population_confidence,
                  pop.payload AS population_payload
                FROM statcan_geography g
                JOIN statcan_denominator pop
                  ON pop.geo_code = g.geo_code
                 AND pop.metric = 'population'
                WHERE g.geo_level = 'CSD'
                ORDER BY g.geo_name
                """
            ).fetchall()
        )

    def business_denominator(self, geo_code: str, category: str) -> dict[str, Any] | None:
        return cast(
            dict[str, Any] | None,
            self.conn.execute(
                """
                SELECT id, value, source_refs, confidence_score
                     , payload
                FROM statcan_denominator
                WHERE geo_code = %s
                  AND metric = 'business_count'
                  AND category = %s
                ORDER BY value DESC
                LIMIT 1
                """,
                (geo_code, category),
            ).fetchone(),
        )

    def operators_for_geo_category(
        self, geo_name: str, category: str
    ) -> list[dict[str, Any]]:
        like_geo = f"%{geo_name.lower()}%"
        return list(
            self.conn.execute(
                """
                SELECT
                  id,
                  name,
                  source_refs,
                  confidence_score,
                  municipality,
                  neighborhood,
                  ST_Y(geom::geometry) AS lat,
                  ST_X(geom::geometry) AS lng,
                  first_seen_at,
                  first_seen_at >= now() - interval '180 days' AS is_new_180d
                FROM "operator"
                WHERE %s = ANY(categories)
                  AND (
                    lower(COALESCE(municipality, '')) = lower(%s)
                    OR lower(COALESCE(neighborhood, '')) = lower(%s)
                    OR lower(COALESCE(address, '')) LIKE %s
                  )
                ORDER BY first_seen_at DESC, name ASC
                """,
                (category, geo_name, geo_name, like_geo),
            ).fetchall()
        )

    def operators_for_category(self, category: str) -> list[dict[str, Any]]:
        return list(
            self.conn.execute(
                """
                SELECT
                  id,
                  name,
                  source_refs,
                  confidence_score,
                  municipality,
                  neighborhood,
                  ST_Y(geom::geometry) AS lat,
                  ST_X(geom::geometry) AS lng,
                  first_seen_at,
                  first_seen_at >= now() - interval '180 days' AS is_new_180d
                FROM "operator"
                WHERE %s = ANY(categories)
                  AND jsonb_array_length(source_refs) > 0
                ORDER BY first_seen_at DESC, name ASC
                """,
                (category,),
            ).fetchall()
        )

    def operators_with_neighborhoods(self) -> list[dict[str, Any]]:
        return list(
            self.conn.execute(
                """
                SELECT
                  id,
                  municipality,
                  neighborhood,
                  ST_Y(geom::geometry) AS lat,
                  ST_X(geom::geometry) AS lng,
                  source_refs,
                  confidence_score
                FROM "operator"
                WHERE neighborhood IS NOT NULL
                  AND trim(neighborhood) <> ''
                  AND municipality IS NOT NULL
                  AND trim(municipality) <> ''
                  AND jsonb_array_length(source_refs) > 0
                """
            ).fetchall()
        )

    def upsert_neighborhood_geography(self, payload: dict[str, Any]) -> bool:
        gate = bc_gate(
            CanonicalGeoRecord(
                source_name=DERIVED_NEIGHBORHOOD_SOURCE,
                title=str(payload["geo_name"]),
                address=None,
                municipality=payload["municipality"],
                province="BC",
                country="CA",
                lat=payload["lat"],
                lng=payload["lng"],
                text=f"{payload['geo_name']}, {payload['municipality']}, BC",
                statcan_geo_code=payload["parent_geo_code"],
                raw=payload,
            )
        )
        if not gate.passes:
            return False
        self.conn.execute(
            """
            INSERT INTO statcan_geography (
              geo_code,
              geo_level,
              geo_name,
              parent_geo_code,
              geom,
              source_name,
              source_refs,
              confidence_score,
              bc_gate_result,
              payload
            )
            VALUES (
              %s,
              'neighborhood',
              %s,
              %s,
              CASE WHEN %s::double precision IS NULL OR %s::double precision IS NULL
                THEN NULL
                ELSE ST_SetSRID(
                  ST_MakePoint(%s::double precision, %s::double precision),
                  4326
                )::geography
              END,
              %s,
              %s,
              %s,
              %s,
              %s
            )
            ON CONFLICT (geo_code) DO UPDATE SET
              geo_level = EXCLUDED.geo_level,
              geo_name = EXCLUDED.geo_name,
              parent_geo_code = EXCLUDED.parent_geo_code,
              geom = EXCLUDED.geom,
              source_name = EXCLUDED.source_name,
              source_refs = EXCLUDED.source_refs,
              confidence_score = EXCLUDED.confidence_score,
              bc_gate_result = EXCLUDED.bc_gate_result,
              payload = EXCLUDED.payload,
              updated_at = now()
            """,
            (
                payload["geo_code"],
                payload["geo_name"],
                payload["parent_geo_code"],
                payload["lng"],
                payload["lat"],
                payload["lng"],
                payload["lat"],
                DERIVED_NEIGHBORHOOD_SOURCE,
                Jsonb(payload["source_refs"]),
                payload["confidence_score"],
                Jsonb(
                    {
                        "passes": gate.passes,
                        "reason": gate.reason,
                        "confidence": gate.confidence,
                    }
                ),
                Jsonb(payload["payload"]),
            ),
        )
        return True

    def signal_count_for_geo_category(
        self, geo_name: str, category: str, days: int
    ) -> tuple[int, list[dict[str, Any]], list[float]]:
        rows = self.conn.execute(
            """
            SELECT s.id, s.source_refs, s.confidence_score
            FROM signal s
            LEFT JOIN "operator" op ON op.id = s.related_operator_id
            WHERE s.occurred_at >= now() - (%s::text || ' days')::interval
              AND (
                %s = ANY(COALESCE(op.categories, ARRAY[]::text[]))
                OR %s = ANY(COALESCE(s.ai_category_suggestions, ARRAY[]::text[]))
              )
              AND (
                lower(COALESCE(op.municipality, '')) = lower(%s)
                OR lower(COALESCE(op.neighborhood, '')) = lower(%s)
                OR lower(COALESCE(op.address, '')) LIKE %s
              )
            """,
            (days, category, category, geo_name, geo_name, f"%{geo_name.lower()}%"),
        ).fetchall()
        refs = _flatten_refs(row["source_refs"] for row in rows)
        confidences = [float(row["confidence_score"]) for row in rows]
        return len(rows), refs, confidences

    def velocity_refs_and_counts(
        self, category: str, days: int
    ) -> tuple[dict[str, int], list[dict[str, Any]], float]:
        operator_rows = self.conn.execute(
            """
            SELECT id, source_refs, confidence_score
            FROM "operator"
            WHERE %s = ANY(categories)
              AND first_seen_at >= now() - (%s::text || ' days')::interval
            """,
            (category, days),
        ).fetchall()
        job_rows = self.conn.execute(
            """
            SELECT id
            FROM job_posting
            WHERE posted_at >= now() - (%s::text || ' days')::interval
              AND job_category = %s
            """,
            (days, category),
        ).fetchall()
        event_rows = self.conn.execute(
            """
            SELECT id, source_refs
            FROM event
            WHERE start_at >= now() - (%s::text || ' days')::interval
              AND %s = ANY(topics)
            """,
            (days, category),
        ).fetchall()
        signal_rows = self.conn.execute(
            """
            SELECT s.id, s.source_refs, s.confidence_score
            FROM signal s
            LEFT JOIN "operator" op ON op.id = s.related_operator_id
            WHERE s.occurred_at >= now() - (%s::text || ' days')::interval
              AND (
                %s = ANY(COALESCE(op.categories, ARRAY[]::text[]))
                OR %s = ANY(COALESCE(s.ai_category_suggestions, ARRAY[]::text[]))
              )
            """,
            (days, category, category),
        ).fetchall()
        refs = _flatten_refs(
            [
                *[row["source_refs"] for row in operator_rows],
                *[row["source_refs"] for row in event_rows],
                *[row["source_refs"] for row in signal_rows],
            ]
        )
        confidences = [
            *[float(row["confidence_score"]) for row in operator_rows],
            *[float(row["confidence_score"]) for row in signal_rows],
        ]
        counts = {
            "new_operator_count": len(operator_rows),
            "job_velocity_count": len(job_rows),
            "event_velocity_count": len(event_rows),
            "news_velocity_count": len(signal_rows),
        }
        confidence = _average(confidences, default=0.5)
        return counts, refs, confidence

    def upsert_heatmap_cell(self, payload: dict[str, Any]) -> None:
        self.conn.execute(
            """
            INSERT INTO opportunity_heatmap_cell (
              id,
              category,
              geo_code,
              geo_name,
              geo_level,
              geom,
              supply_count,
              operator_ids,
              population,
              business_count,
              demand_proxy,
              low_supply_density,
              category_growth,
              target_demo_fit,
              transit_access,
              event_community_activity,
              source_confidence,
              opportunity_score,
              component_breakdown,
              calculation_method,
              source_refs,
              confidence_score,
              trace_payload
            )
            VALUES (
              %s, %s, %s, %s, %s,
              CASE WHEN %s::double precision IS NULL OR %s::double precision IS NULL
                THEN NULL
                ELSE ST_SetSRID(
                  ST_MakePoint(%s::double precision, %s::double precision),
                  4326
                )::geography
              END,
              %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (category, geo_code) DO UPDATE SET
              geom = EXCLUDED.geom,
              supply_count = EXCLUDED.supply_count,
              operator_ids = EXCLUDED.operator_ids,
              population = EXCLUDED.population,
              business_count = EXCLUDED.business_count,
              demand_proxy = EXCLUDED.demand_proxy,
              low_supply_density = EXCLUDED.low_supply_density,
              category_growth = EXCLUDED.category_growth,
              target_demo_fit = EXCLUDED.target_demo_fit,
              transit_access = EXCLUDED.transit_access,
              event_community_activity = EXCLUDED.event_community_activity,
              source_confidence = EXCLUDED.source_confidence,
              opportunity_score = EXCLUDED.opportunity_score,
              component_breakdown = EXCLUDED.component_breakdown,
              calculation_method = EXCLUDED.calculation_method,
              source_refs = EXCLUDED.source_refs,
              confidence_score = EXCLUDED.confidence_score,
              trace_payload = EXCLUDED.trace_payload,
              generated_at = now()
            """,
            (
                payload["id"],
                payload["category"],
                payload["geo_code"],
                payload["geo_name"],
                payload["geo_level"],
                payload["lng"],
                payload["lat"],
                payload["lng"],
                payload["lat"],
                payload["supply_count"],
                payload["operator_ids"],
                payload["population"],
                payload["business_count"],
                payload["components"]["demand_proxy"],
                payload["components"]["low_supply_density"],
                payload["components"]["category_growth"],
                payload["components"]["target_demo_fit"],
                payload["components"]["transit_access"],
                payload["components"]["event_community_activity"],
                payload["components"]["source_confidence"],
                payload["opportunity_score"],
                Jsonb(payload["component_breakdown"]),
                payload["calculation_method"],
                Jsonb(payload["source_refs"]),
                payload["confidence_score"],
                Jsonb(payload["trace_payload"]),
            ),
        )

    def upsert_scorecard(self, payload: dict[str, Any]) -> None:
        self.conn.execute(
            """
            INSERT INTO opportunity_scorecard (
              id,
              category,
              geo_code,
              geo_name,
              geo_level,
              opportunity_score,
              component_breakdown,
              source_refs,
              confidence_score,
              calculation_method,
              caveat
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (category, geo_code) DO UPDATE SET
              geo_level = EXCLUDED.geo_level,
              opportunity_score = EXCLUDED.opportunity_score,
              component_breakdown = EXCLUDED.component_breakdown,
              source_refs = EXCLUDED.source_refs,
              confidence_score = EXCLUDED.confidence_score,
              calculation_method = EXCLUDED.calculation_method,
              caveat = EXCLUDED.caveat,
              generated_at = now()
            """,
            (
                stable_id("score", payload["category"], payload["geo_code"]),
                payload["category"],
                payload["geo_code"],
                payload["geo_name"],
                payload["geo_level"],
                payload["opportunity_score"],
                Jsonb(payload["component_breakdown"]),
                Jsonb(payload["source_refs"]),
                payload["confidence_score"],
                payload["calculation_method"],
                "Supply-demand signal only; not a guarantee of economic attractiveness.",
            ),
        )

    def upsert_velocity(
        self,
        category: str,
        days: int,
        counts: dict[str, int],
        refs: list[dict[str, Any]],
        confidence: float,
    ) -> None:
        component_breakdown = {
            **counts,
            "window_days": days,
            "source_confidence": confidence,
            "method": (
                "Counts are based on source-backed operators, jobs, events, "
                "and signals observed inside the rolling window."
            ),
        }
        self.conn.execute(
            """
            INSERT INTO category_velocity (
              id,
              category,
              window_days,
              new_operator_count,
              job_velocity_count,
              event_velocity_count,
              news_velocity_count,
              component_breakdown,
              source_refs,
              confidence_score
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (category, window_days) DO UPDATE SET
              new_operator_count = EXCLUDED.new_operator_count,
              job_velocity_count = EXCLUDED.job_velocity_count,
              event_velocity_count = EXCLUDED.event_velocity_count,
              news_velocity_count = EXCLUDED.news_velocity_count,
              component_breakdown = EXCLUDED.component_breakdown,
              source_refs = EXCLUDED.source_refs,
              confidence_score = EXCLUDED.confidence_score,
              calculated_at = now()
            """,
            (
                stable_id("velocity", category, days),
                category,
                days,
                counts["new_operator_count"],
                counts["job_velocity_count"],
                counts["event_velocity_count"],
                counts["news_velocity_count"],
                Jsonb(component_breakdown),
                Jsonb(refs),
                confidence,
            ),
        )


def run_opportunity_analytics(
    repository: OpportunityAnalyticsRepository | None = None,
) -> RunMetrics:
    repo = repository or OpportunityAnalyticsRepository()
    metrics = RunMetrics()
    try:
        categories = repo.categories_with_denominators()
        geographies = repo.geographies()
        max_population = max((float(geo["population"]) for geo in geographies), default=1.0)
        neighborhood_denominator = _neighborhood_denominator_context(
            repo.operators_with_neighborhoods()
        )

        for category in categories:
            category_operators = repo.operators_for_category(category)
            raw_rows: list[dict[str, Any]] = []
            max_density = 0.0
            max_activity = 0
            max_growth = 0
            for geo in geographies:
                denominator = repo.business_denominator(str(geo["geo_code"]), category)
                if denominator is None:
                    continue
                operators = _operators_for_csd(category_operators, str(geo["geo_name"]))
                signal_count, signal_refs, signal_conf = repo.signal_count_for_geo_category(
                    str(geo["geo_name"]), category, 180
                )
                population = float(geo["population"])
                supply_count = len(operators)
                density = supply_count / max(population / 10000, 1)
                max_density = max(max_density, density)
                max_activity = max(max_activity, signal_count)
                new_operators = sum(1 for operator in operators if operator["is_new_180d"])
                max_growth = max(max_growth, new_operators)
                nearest_competitors = _competitors_within_radius(
                    category_operators,
                    _optional_float(geo["lat"]),
                    _optional_float(geo["lng"]),
                    COMPETITOR_RADIUS_KM,
                )
                raw_rows.append(
                    {
                        "geo": geo,
                        "denominator": denominator,
                        "operators": operators,
                        "signal_count": signal_count,
                        "signal_refs": signal_refs,
                        "signal_conf": signal_conf,
                        "density": density,
                        "new_operators": new_operators,
                        "nearest_competitors": nearest_competitors,
                        "competitor_count_within_radius": len(nearest_competitors),
                        "competitor_radius_km": COMPETITOR_RADIUS_KM,
                        "demand": _demand_metadata(
                            geography_payload=geo.get("geography_payload"),
                            population_payload=geo.get("population_payload"),
                            business_payload=denominator.get("payload"),
                            denominator_scope="CSD",
                        ),
                    }
                )
            neighborhood_rows = _neighborhood_rows_for_category(
                repo=repo,
                category=category,
                category_operators=category_operators,
                csd_geographies=geographies,
                neighborhood_context=neighborhood_denominator,
            )
            for row in neighborhood_rows:
                max_density = max(max_density, float(row["density"]))
                max_activity = max(max_activity, int(row["signal_count"]))
                max_growth = max(max_growth, int(row["new_operators"]))
            raw_rows.extend(neighborhood_rows)
            metrics.records_fetched += len(raw_rows)
            for row in raw_rows:
                payload = _payload_for_cell(
                    category=category,
                    row=row,
                    max_population=max_population,
                    max_density=max_density,
                    max_activity=max_activity,
                    max_growth=max_growth,
                )
                if not _has_complete_score(payload):
                    continue
                repo.upsert_heatmap_cell(payload)
                repo.upsert_scorecard(payload)
                metrics.records_persisted += 1

        for category in categories:
            for days in (30, 90, 180):
                counts, refs, confidence = repo.velocity_refs_and_counts(category, days)
                if not refs:
                    refs = _category_method_refs(category)
                repo.upsert_velocity(category, days, counts, refs, confidence)
                metrics.records_persisted += 1
        return metrics
    finally:
        repo.close()


def _payload_for_cell(
    *,
    category: str,
    row: dict[str, Any],
    max_population: float,
    max_density: float,
    max_activity: int,
    max_growth: int,
) -> dict[str, Any]:
    geo = row["geo"]
    denominator = row["denominator"]
    operators = row["operators"]
    population = float(geo["population"])
    business_count = float(denominator["value"])
    supply_count = len(operators)
    demand_proxy = _clamp(population / max_population)
    low_supply_density = _clamp(1 - (row["density"] / max(max_density, 0.0001)))
    category_growth = _clamp(row["new_operators"] / max(max_growth, 1))
    business_density = min(business_count / max(population / 10000, 1), 1)
    target_demo_fit = _clamp((demand_proxy + business_density) / 2)
    transit_access = _core_access_proxy(geo["lat"], geo["lng"])
    event_community_activity = _clamp(row["signal_count"] / max(max_activity, 1))
    demand = row.get("demand", {})
    confidences = [
        float(geo["geography_confidence"]),
        float(geo["population_confidence"]),
        float(denominator["confidence_score"]),
        *[float(operator["confidence_score"]) for operator in operators],
        *row["signal_conf"],
    ]
    source_confidence = _average(confidences, default=0.5) * float(
        demand.get("quality_multiplier", 1.0)
    )
    source_confidence = _clamp(source_confidence)
    components = ScoreComponents(
        demand_proxy=round(demand_proxy, 4),
        low_supply_density=round(low_supply_density, 4),
        category_growth=round(category_growth, 4),
        target_demo_fit=round(target_demo_fit, 4),
        transit_access=round(transit_access, 4),
        event_community_activity=round(event_community_activity, 4),
        source_confidence=round(source_confidence, 4),
    )
    operator_ids = [str(operator["id"]) for operator in operators]
    source_refs = _unique_refs(
        [
            *list(geo["geography_source_refs"]),
            *list(geo["population_source_refs"]),
            *list(denominator["source_refs"]),
            *_flatten_refs(operator["source_refs"] for operator in operators),
            *row["signal_refs"],
        ]
    )
    calculation_method = (
        f"{OPPORTUNITY_METHOD} {NEIGHBORHOOD_METHOD}"
        if str(geo["geo_level"]) == "neighborhood"
        else OPPORTUNITY_METHOD
    )
    component_breakdown = {
        **components.as_dict(),
        "formula": calculation_method,
        "inputs": {
            "population_denominator_id": geo["population_denominator_id"],
            "business_denominator_id": denominator["id"],
            "operator_ids": operator_ids,
            "signal_count_180d": row["signal_count"],
            "supply_density_per_10000_population": round(row["density"], 4),
            "competitor_count_within_radius": row.get(
                "competitor_count_within_radius", supply_count
            ),
            "competitor_radius_km": row.get("competitor_radius_km", COMPETITOR_RADIUS_KM),
            "nearest_competitors": row.get("nearest_competitors", []),
            "demand_source": demand.get("demand_source", "unknown"),
            "demand_source_status": demand.get("demand_source_status", "unknown"),
            "denominator_scope": demand.get("denominator_scope", geo["geo_level"]),
            "raw_population": round(population, 4),
            "raw_business_count": round(business_count, 4),
            "raw_parent_population": demand.get("raw_parent_population"),
            "raw_parent_business_count": demand.get("raw_parent_business_count"),
            "population_allocation_share": demand.get("population_allocation_share"),
            "business_allocation_share": demand.get("business_allocation_share"),
            "population_estimation_method": demand.get("population_estimation_method"),
            "business_estimation_method": demand.get("business_estimation_method"),
        },
    }
    return {
        "id": stable_id("heat", category, geo["geo_code"]),
        "category": category,
        "geo_code": str(geo["geo_code"]),
        "geo_name": str(geo["geo_name"]),
        "geo_level": str(geo["geo_level"]),
        "lat": float(geo["lat"]) if geo["lat"] is not None else None,
        "lng": float(geo["lng"]) if geo["lng"] is not None else None,
        "supply_count": supply_count,
        "operator_ids": operator_ids,
        "population": population,
        "business_count": business_count,
        "components": components.as_dict(),
        "opportunity_score": components.score(),
        "component_breakdown": component_breakdown,
        "calculation_method": calculation_method,
        "source_refs": source_refs,
        "confidence_score": source_confidence,
        "trace_payload": component_breakdown["inputs"],
    }


def _has_complete_score(payload: dict[str, Any]) -> bool:
    component_values = payload["components"].values()
    return bool(payload["source_refs"]) and all(value is not None for value in component_values)


def _neighborhood_rows_for_category(
    *,
    repo: OpportunityAnalyticsRepository,
    category: str,
    category_operators: list[dict[str, Any]],
    csd_geographies: list[dict[str, Any]],
    neighborhood_context: dict[str, Any],
) -> list[dict[str, Any]]:
    csd_by_name = {_key(geo["geo_name"]): geo for geo in csd_geographies}
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for operator in category_operators:
        municipality = _clean_text(operator.get("municipality"))
        neighborhood = _clean_text(operator.get("neighborhood"))
        if not municipality or not neighborhood:
            continue
        if (
            _optional_float(operator.get("lat")) is None
            or _optional_float(operator.get("lng")) is None
        ):
            continue
        grouped[(_key(municipality), _key(neighborhood))].append(operator)

    rows: list[dict[str, Any]] = []
    for (municipality_key, neighborhood_key), operators in grouped.items():
        parent_geo = csd_by_name.get(municipality_key)
        if parent_geo is None:
            continue
        denominator = repo.business_denominator(str(parent_geo["geo_code"]), category)
        if denominator is None:
            continue
        municipality = _clean_text(operators[0].get("municipality")) or str(parent_geo["geo_name"])
        neighborhood = _clean_text(operators[0].get("neighborhood")) or neighborhood_key
        total_tagged = int(
            neighborhood_context["counts_by_municipality"].get(municipality_key, len(operators))
        )
        neighborhood_tagged = int(
            neighborhood_context["counts_by_key"].get(
                (municipality_key, neighborhood_key), len(operators)
            )
        )
        allocation_share = _clamp(neighborhood_tagged / max(total_tagged, 1))
        if allocation_share <= 0:
            continue
        population = float(parent_geo["population"]) * allocation_share
        business_count = float(denominator["value"]) * allocation_share
        lat = _average(
            [_optional_float(operator.get("lat")) for operator in operators],
            default=float(parent_geo["lat"]),
        )
        lng = _average(
            [_optional_float(operator.get("lng")) for operator in operators],
            default=float(parent_geo["lng"]),
        )
        geo_code = stable_id("nh", parent_geo["geo_code"], neighborhood)
        operator_refs = _flatten_refs(operator["source_refs"] for operator in operators)
        source_refs = _unique_refs(
            [
                *list(parent_geo["geography_source_refs"]),
                *list(parent_geo["population_source_refs"]),
                *list(denominator["source_refs"]),
                *operator_refs,
            ]
        )
        nearest_competitors = _competitors_within_radius(
            category_operators,
            lat,
            lng,
            COMPETITOR_RADIUS_KM,
        )
        geography_confidence = _clamp(
            _average(
                [
                    float(parent_geo["geography_confidence"]),
                    *[float(operator["confidence_score"]) for operator in operators],
                ],
                default=0.7,
            )
            * 0.88
        )
        geography_payload = {
            "source": DERIVED_NEIGHBORHOOD_SOURCE,
            "parent_geo_code": parent_geo["geo_code"],
            "parent_geo_name": parent_geo["geo_name"],
            "operator_neighborhood_tag_count": neighborhood_tagged,
            "municipality_neighborhood_tag_count": total_tagged,
            "population_allocation_share": round(allocation_share, 6),
            "method": NEIGHBORHOOD_METHOD,
        }
        if not repo.upsert_neighborhood_geography(
            {
                "geo_code": geo_code,
                "geo_name": neighborhood,
                "municipality": municipality,
                "parent_geo_code": parent_geo["geo_code"],
                "lat": lat,
                "lng": lng,
                "source_refs": source_refs,
                "confidence_score": geography_confidence,
                "payload": geography_payload,
            }
        ):
            continue
        signal_count, signal_refs, signal_conf = repo.signal_count_for_geo_category(
            neighborhood, category, 180
        )
        supply_count = len(operators)
        density = supply_count / max(population / 10000, 1)
        new_operators = sum(1 for operator in operators if operator["is_new_180d"])
        derived_denominator = {
            "id": stable_id("den_neighborhood", denominator["id"], geo_code),
            "value": business_count,
            "source_refs": denominator["source_refs"],
            "confidence_score": _clamp(float(denominator["confidence_score"]) * 0.88),
            "payload": {
                **dict(denominator.get("payload") or {}),
                "denominator_scope": "neighborhood_estimate_from_parent_csd",
                "raw_parent_business_count": float(denominator["value"]),
                "business_allocation_share": round(allocation_share, 6),
            },
        }
        geo = {
            "geo_code": geo_code,
            "geo_level": "neighborhood",
            "geo_name": neighborhood,
            "lat": lat,
            "lng": lng,
            "geography_source_refs": source_refs,
            "geography_confidence": geography_confidence,
            "geography_payload": geography_payload,
            "population_denominator_id": stable_id(
                "den_neighborhood_population", parent_geo["population_denominator_id"], geo_code
            ),
            "population": population,
            "population_source_refs": parent_geo["population_source_refs"],
            "population_confidence": _clamp(float(parent_geo["population_confidence"]) * 0.88),
            "population_payload": {
                **dict(parent_geo.get("population_payload") or {}),
                "denominator_scope": "neighborhood_estimate_from_parent_csd",
                "raw_parent_population": float(parent_geo["population"]),
                "population_allocation_share": round(allocation_share, 6),
            },
            "municipality": municipality,
            "parent_geo_code": parent_geo["geo_code"],
        }
        rows.append(
            {
                "geo": geo,
                "denominator": derived_denominator,
                "operators": operators,
                "signal_count": signal_count,
                "signal_refs": signal_refs,
                "signal_conf": signal_conf,
                "density": density,
                "new_operators": new_operators,
                "nearest_competitors": nearest_competitors,
                "competitor_count_within_radius": len(nearest_competitors),
                "competitor_radius_km": COMPETITOR_RADIUS_KM,
                "demand": _demand_metadata(
                    geography_payload=geo["geography_payload"],
                    population_payload=geo["population_payload"],
                    business_payload=derived_denominator["payload"],
                    denominator_scope="neighborhood_estimate_from_parent_csd",
                    raw_parent_population=float(parent_geo["population"]),
                    raw_parent_business_count=float(denominator["value"]),
                    population_allocation_share=allocation_share,
                    business_allocation_share=allocation_share,
                ),
            }
        )
    return rows


def _neighborhood_denominator_context(
    operators: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    counts_by_municipality: dict[str, int] = defaultdict(int)
    counts_by_key: dict[tuple[str, str], int] = defaultdict(int)
    for operator in operators:
        municipality = _clean_text(operator.get("municipality"))
        neighborhood = _clean_text(operator.get("neighborhood"))
        if not municipality or not neighborhood:
            continue
        municipality_key = _key(municipality)
        neighborhood_key = _key(neighborhood)
        counts_by_municipality[municipality_key] += 1
        counts_by_key[(municipality_key, neighborhood_key)] += 1
    return {
        "counts_by_municipality": dict(counts_by_municipality),
        "counts_by_key": dict(counts_by_key),
    }


def _operators_for_csd(
    operators: Sequence[dict[str, Any]], geo_name: str
) -> list[dict[str, Any]]:
    geo_key = _key(geo_name)
    return [
        operator
        for operator in operators
        if _key(operator.get("municipality")) == geo_key
        or _key(operator.get("neighborhood")) == geo_key
    ]


def _competitors_within_radius(
    operators: Sequence[dict[str, Any]],
    lat: float | None,
    lng: float | None,
    radius_km: float,
) -> list[dict[str, Any]]:
    if lat is None or lng is None:
        return []
    competitors: list[dict[str, Any]] = []
    for operator in operators:
        operator_lat = _optional_float(operator.get("lat"))
        operator_lng = _optional_float(operator.get("lng"))
        if operator_lat is None or operator_lng is None:
            continue
        distance_km = _haversine_km(lat, lng, operator_lat, operator_lng)
        if distance_km > radius_km:
            continue
        competitors.append(
            {
                "operator_id": str(operator["id"]),
                "name": str(operator["name"]),
                "distance_km": round(distance_km, 2),
                "municipality": operator.get("municipality"),
                "neighborhood": operator.get("neighborhood"),
                "source_refs": _unique_refs(operator.get("source_refs") or []),
            }
        )
    return sorted(
        competitors,
        key=lambda item: (float(item["distance_km"]), str(item["name"]).lower()),
    )


def _competitor_count_within_radius(
    operators: Sequence[dict[str, Any]],
    lat: float | None,
    lng: float | None,
    radius_km: float,
) -> int:
    if lat is None or lng is None:
        return 0
    count = 0
    for operator in operators:
        operator_lat = _optional_float(operator.get("lat"))
        operator_lng = _optional_float(operator.get("lng"))
        if operator_lat is None or operator_lng is None:
            continue
        if _haversine_km(lat, lng, operator_lat, operator_lng) <= radius_km:
            count += 1
    return count


def _demand_metadata(
    *,
    geography_payload: Any,
    population_payload: Any,
    business_payload: Any,
    denominator_scope: str,
    raw_parent_population: float | None = None,
    raw_parent_business_count: float | None = None,
    population_allocation_share: float | None = None,
    business_allocation_share: float | None = None,
) -> dict[str, Any]:
    payloads = [
        payload
        for payload in (geography_payload, population_payload, business_payload)
        if isinstance(payload, dict)
    ]
    demand_source = next(
        (
            str(payload.get("demand_source"))
            for payload in payloads
            if payload.get("demand_source")
        ),
        "statcan_wds_live",
    )
    demand_source_status = next(
        (
            str(payload.get("demand_source_status"))
            for payload in payloads
            if payload.get("demand_source_status")
        ),
        "live",
    )
    multiplier = 1.0
    if "fixture" in demand_source or "fixture" in demand_source_status:
        multiplier *= 0.92
    if denominator_scope != "CSD":
        multiplier *= 0.88
    return {
        "demand_source": demand_source,
        "demand_source_status": demand_source_status,
        "denominator_scope": denominator_scope,
        "quality_multiplier": multiplier,
        "live_attempted": any(bool(payload.get("live_attempted")) for payload in payloads),
        "live_error": next(
            (payload.get("live_error") for payload in payloads if payload.get("live_error")),
            None,
        ),
        "raw_parent_population": raw_parent_population,
        "raw_parent_business_count": raw_parent_business_count,
        "population_allocation_share": (
            round(population_allocation_share, 6)
            if population_allocation_share is not None
            else None
        ),
        "business_allocation_share": (
            round(business_allocation_share, 6)
            if business_allocation_share is not None
            else None
        ),
        "population_estimation_method": (
            "parent CSD population allocated by observed neighborhood-tagged operator share"
            if denominator_scope != "CSD"
            else "official CSD denominator"
        ),
        "business_estimation_method": (
            "parent CSD category business count allocated by observed "
            "neighborhood-tagged operator share"
            if denominator_scope != "CSD"
            else "official CSD denominator"
        ),
    }


def _core_access_proxy(lat: float | None, lng: float | None) -> float:
    if lat is None or lng is None:
        return 0.5
    # Waterfront Station proxy, derived only from stored CSD centroids.
    km = _haversine_km(lat, lng, 49.2859, -123.1113)
    return _clamp(1 - (km / 35))


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _average(values: Iterable[float | None], *, default: float) -> float:
    cleaned = [value for value in values if value is not None]
    if not cleaned:
        return default
    return sum(cleaned) / len(cleaned)


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, str | int | float):
        return float(value)
    return None


def _clean_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _key(value: object) -> str:
    return str(value or "").strip().lower()


def _flatten_refs(ref_groups: Iterable[Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for group in ref_groups:
        if isinstance(group, list):
            refs.extend(cast(list[dict[str, Any]], group))
    return _unique_refs(refs)


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


def _category_method_refs(category: str) -> list[dict[str, Any]]:
    return [
        {
            "source_name": "category_taxonomy",
            "url": "docs/analytics/category_naics_crosswalk.md",
            "trust_tier": "official",
            "seen_at": "2026-06-18T00:00:00Z",
            "source_record_id": category,
            "licence": None,
        }
    ]
