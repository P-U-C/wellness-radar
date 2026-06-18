from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, cast

from psycopg.types.json import Jsonb

from apps.jobs.runner import DatabaseRepository, RunMetrics
from packages.shared.ids import stable_id

OPPORTUNITY_METHOD = (
    "M3 v1: 0.30 demand_proxy + 0.20 low_supply_density + 0.15 category_growth "
    "+ 0.15 target_demo_fit + 0.10 transit_access + 0.05 event_community_activity "
    "+ 0.05 source_confidence. White-space means a supply-demand signal, not "
    "guaranteed economic attractiveness."
)


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
                  pop.id AS population_denominator_id,
                  pop.value AS population,
                  pop.source_refs AS population_source_refs,
                  pop.confidence_score AS population_confidence
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
              opportunity_score,
              component_breakdown,
              source_refs,
              confidence_score,
              calculation_method,
              caveat
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (category, geo_code) DO UPDATE SET
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
        metrics.records_fetched = len(categories) * len(geographies)
        max_population = max((float(geo["population"]) for geo in geographies), default=1.0)

        for category in categories:
            raw_rows: list[dict[str, Any]] = []
            max_density = 0.0
            max_activity = 0
            max_growth = 0
            for geo in geographies:
                denominator = repo.business_denominator(str(geo["geo_code"]), category)
                if denominator is None:
                    continue
                operators = repo.operators_for_geo_category(str(geo["geo_name"]), category)
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
                    }
                )
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
    confidences = [
        float(geo["geography_confidence"]),
        float(geo["population_confidence"]),
        float(denominator["confidence_score"]),
        *[float(operator["confidence_score"]) for operator in operators],
        *row["signal_conf"],
    ]
    source_confidence = _average(confidences, default=0.5)
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
    component_breakdown = {
        **components.as_dict(),
        "formula": OPPORTUNITY_METHOD,
        "inputs": {
            "population_denominator_id": geo["population_denominator_id"],
            "business_denominator_id": denominator["id"],
            "operator_ids": operator_ids,
            "signal_count_180d": row["signal_count"],
            "supply_density_per_10000_population": round(row["density"], 4),
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
        "calculation_method": OPPORTUNITY_METHOD,
        "source_refs": source_refs,
        "confidence_score": source_confidence,
        "trace_payload": component_breakdown["inputs"],
    }


def _has_complete_score(payload: dict[str, Any]) -> bool:
    component_values = payload["components"].values()
    return bool(payload["source_refs"]) and all(value is not None for value in component_values)


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


def _average(values: Iterable[float], *, default: float) -> float:
    cleaned = [value for value in values if value is not None]
    if not cleaned:
        return default
    return sum(cleaned) / len(cleaned)


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
