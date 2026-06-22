from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from psycopg.types.json import Jsonb

from apps.jobs.runner import DatabaseRepository, RunMetrics
from packages.shared.ids import slugify, stable_id
from packages.shared.normalizers import normalize_name

BUNDLE_METHOD_VERSION = "r1_bundle_synthesis_v1"
BUNDLE_SCORE_FORMULA = (
    "0.30 demand_proxy + 0.20 member_scale + 0.20 low_supply_density "
    "+ 0.20 momentum + 0.10 source_confidence"
)
BUNDLE_METHOD_REF = {
    "source_name": "bundle_synthesis_taxonomy",
    "url": "apps/jobs/analytics/bundles.py",
    "trust_tier": "informal",
    "seen_at": "2026-06-22T00:00:00Z",
    "source_record_id": BUNDLE_METHOD_VERSION,
    "licence": None,
}
OSM_SUBTYPE_TAG_KEYS = {"leisure", "amenity", "sport", "healthcare", "shop", "massage"}
RAW_TEXT_FIELDS = (
    "businesstype",
    "businesssubtype",
    "businessdescription",
    "businessname",
    "name",
    "categories",
)


@dataclass(frozen=True)
class BundleDefinition:
    slug: str
    label: str
    description: str
    category_terms: tuple[str, ...]
    keyword_terms: tuple[str, ...]
    tag_terms: tuple[str, ...]


# Extensible taxonomy: add a BundleDefinition with category, keyword, or tag
# evidence. Membership remains data-driven: an operator joins only when its stored
# categories, OSM/source subtype tags, or source-backed name text match.
BUNDLE_TAXONOMY: tuple[BundleDefinition, ...] = (
    BundleDefinition(
        slug="cold_plunge_contrast_therapy",
        label="Cold plunge & contrast therapy",
        description="Cold plunge, contrast therapy, sauna, cryotherapy, float, and recovery rooms.",
        category_terms=("recovery_contrast_therapy",),
        keyword_terms=(
            "cold plunge",
            "contrast",
            "kontrast",
            "cryo",
            "cryotherapy",
            "float",
            "sauna",
            "bathhouse",
            "recovery",
            "restore",
        ),
        tag_terms=("leisure=sauna",),
    ),
    BundleDefinition(
        slug="spa_thermal",
        label="Spa & thermal",
        description="Spa, massage, steam, thermal, sauna, and body treatment operators.",
        category_terms=("spa_thermal",),
        keyword_terms=("spa", "massage", "thermal", "steam", "sauna", "esthetic"),
        tag_terms=(
            "amenity=spa",
            "shop=massage",
            "healthcare=massage",
            "leisure=sauna",
        ),
    ),
    BundleDefinition(
        slug="boutique_strength",
        label="Boutique strength",
        description="Gyms, personal training, fitness studios, and strength-oriented facilities.",
        category_terms=("fitness_movement",),
        keyword_terms=("strength", "gym", "fitness", "training", "crossfit", "conditioning"),
        tag_terms=("leisure=fitness_centre", "sport=fitness", "sport=weightlifting"),
    ),
    BundleDefinition(
        slug="yoga_pilates",
        label="Yoga & pilates",
        description="Yoga, pilates, barre, reformer, and adjacent class-based movement.",
        category_terms=(),
        keyword_terms=("yoga", "pilates", "reformer", "barre"),
        tag_terms=("sport=yoga", "sport=pilates"),
    ),
    BundleDefinition(
        slug="longevity_iv",
        label="Longevity / IV",
        description="Longevity, IV, vitamin, infusion, NAD, and preventive optimization services.",
        category_terms=("nutrition_longevity", "preventive_diagnostic"),
        keyword_terms=("longevity", "iv", "infusion", "nad", "vitamin", "diagnostic"),
        tag_terms=("healthcare=laboratory",),
    ),
    BundleDefinition(
        slug="allied_health_bodywork",
        label="Allied health & bodywork",
        description=(
            "Physiotherapy, chiropractic, acupuncture, naturopathic, massage, "
            "and RMT clinics."
        ),
        category_terms=("allied_health",),
        keyword_terms=(
            "physio",
            "physiotherapy",
            "chiro",
            "chiropractic",
            "acupuncture",
            "naturopath",
            "kinesiology",
            "rmt",
            "massage",
        ),
        tag_terms=(
            "healthcare=physiotherapist",
            "healthcare=alternative",
            "healthcare=massage",
            "shop=massage",
        ),
    ),
    BundleDefinition(
        slug="social_wellness_clubs",
        label="Social wellness clubs",
        description=(
            "Community wellness, group recovery, social bathhouse, and membership "
            "club models."
        ),
        category_terms=("community_social_wellness",),
        keyword_terms=("community", "social wellness", "club", "group", "membership"),
        tag_terms=(),
    ),
    BundleDefinition(
        slug="mind_breathwork",
        label="Mind & breathwork",
        description="Meditation, mindfulness, breathwork, and mind-body studios.",
        category_terms=("mind_meditation",),
        keyword_terms=("meditation", "mindfulness", "breathwork"),
        tag_terms=(),
    ),
    BundleDefinition(
        slug="wellness_retail",
        label="Wellness retail",
        description="Supplements, health food, natural products, and wellness retail storefronts.",
        category_terms=("wellness_retail_product",),
        keyword_terms=("supplement", "health food", "natural product", "retail"),
        tag_terms=("shop=health_food", "shop=nutrition_supplements"),
    ),
)


class BundleAnalyticsRepository(DatabaseRepository):
    def operators_for_bundling(self) -> list[dict[str, Any]]:
        return list(
            self.conn.execute(
                """
                SELECT
                  op.id,
                  op.name,
                  op.normalized_name,
                  op.organization_id,
                  org.name AS organization_name,
                  op.categories,
                  op.municipality,
                  op.neighborhood,
                  ST_Y(op.geom::geometry) AS lat,
                  ST_X(op.geom::geometry) AS lng,
                  op.first_seen_at,
                  op.source_refs,
                  op.confidence_score,
                  raw.raw_payloads
                FROM "operator" op
                LEFT JOIN organization org ON org.id = op.organization_id
                LEFT JOIN LATERAL (
                  SELECT COALESCE(jsonb_agg(rp.raw_json), '[]'::jsonb) AS raw_payloads
                  FROM jsonb_array_elements(op.source_refs) AS ref
                  JOIN raw_payload rp
                    ON rp.source_name = ref->>'source_name'
                   AND rp.source_record_id = ref->>'source_record_id'
                ) raw ON TRUE
                WHERE op.geom IS NOT NULL
                  AND jsonb_array_length(op.source_refs) > 0
                ORDER BY op.name ASC
                """
            ).fetchall()
        )

    def geographies_for_scoring(self) -> list[dict[str, Any]]:
        return list(
            self.conn.execute(
                """
                SELECT
                  g.geo_code,
                  g.geo_level,
                  g.geo_name,
                  g.parent_geo_code,
                  COALESCE(parent.geo_name, g.geo_name) AS municipality,
                  g.source_refs AS geography_source_refs,
                  g.confidence_score AS geography_confidence,
                  g.payload AS geography_payload,
                  pop.id AS population_denominator_id,
                  pop.value AS population,
                  pop.source_refs AS population_source_refs,
                  pop.confidence_score AS population_confidence,
                  pop.payload AS population_payload
                FROM statcan_geography g
                LEFT JOIN statcan_geography parent ON parent.geo_code = g.parent_geo_code
                LEFT JOIN statcan_denominator pop
                  ON pop.geo_code = g.geo_code
                 AND pop.metric = 'population'
                WHERE g.geo_level IN ('CSD', 'neighborhood')
                  AND jsonb_array_length(g.source_refs) > 0
                ORDER BY g.geo_level, g.geo_name
                """
            ).fetchall()
        )

    def signals_for_operator_ids(self, operator_ids: Sequence[str]) -> list[dict[str, Any]]:
        if not operator_ids:
            return []
        return list(
            self.conn.execute(
                """
                SELECT
                  id,
                  type,
                  severity::text AS severity,
                  title,
                  occurred_at,
                  related_operator_id,
                  source_refs,
                  confidence_score
                FROM signal
                WHERE related_operator_id = ANY(%s)
                  AND jsonb_array_length(source_refs) > 0
                ORDER BY occurred_at DESC
                LIMIT 1000
                """,
                (list(operator_ids),),
            ).fetchall()
        )

    def people_for_bundles(self) -> list[dict[str, Any]]:
        return list(
            self.conn.execute(
                """
                SELECT
                  p.id,
                  p.name,
                  p.roles,
                  p.affiliations,
                  p.public_profiles,
                  COALESCE(pic.influence_score, p.influence_score) AS influence_score,
                  p.confidence_score,
                  p.source_refs,
                  pic.source_refs AS influence_source_refs
                FROM person p
                LEFT JOIN person_influence_component pic ON pic.person_id = p.id
                WHERE jsonb_array_length(p.source_refs) > 0
                """
            ).fetchall()
        )

    def replace_bundles(self, bundles: Sequence[dict[str, Any]]) -> None:
        self.conn.execute("DELETE FROM bundle_person")
        self.conn.execute("DELETE FROM bundle_operator_membership")
        self.conn.execute("DELETE FROM bundle")
        for bundle in bundles:
            self.conn.execute(
                """
                INSERT INTO bundle (
                  id,
                  label,
                  slug,
                  bundle_score,
                  components,
                  geography,
                  member_count,
                  supporting_signals,
                  source_refs,
                  confidence_score
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    bundle["id"],
                    bundle["label"],
                    bundle["slug"],
                    bundle["bundle_score"],
                    Jsonb(bundle["components"]),
                    Jsonb(bundle["geography"]),
                    bundle["member_count"],
                    Jsonb(bundle["supporting_signals"]),
                    Jsonb(bundle["source_refs"]),
                    bundle["confidence_score"],
                ),
            )
            for membership in bundle["memberships"]:
                self.conn.execute(
                    """
                    INSERT INTO bundle_operator_membership (
                      bundle_id,
                      operator_id,
                      match_reasons,
                      source_refs,
                      confidence_score
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        bundle["id"],
                        membership["operator_id"],
                        Jsonb(membership["match_reasons"]),
                        Jsonb(membership["source_refs"]),
                        membership["confidence_score"],
                    ),
                )
            for person in bundle["top_people"]:
                self.conn.execute(
                    """
                    INSERT INTO bundle_person (
                      bundle_id,
                      person_id,
                      rank,
                      influence_score,
                      why_appears,
                      source_refs,
                      confidence_score
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        bundle["id"],
                        person["id"],
                        person["rank"],
                        person["influence_score"],
                        person["why_appears"],
                        Jsonb(person["source_refs"]),
                        person["confidence_score"],
                    ),
                )


def run_bundle_synthesis(
    repository: BundleAnalyticsRepository | None = None,
) -> RunMetrics:
    repo = repository or BundleAnalyticsRepository()
    metrics = RunMetrics()
    try:
        operators = repo.operators_for_bundling()
        operator_ids = [str(operator["id"]) for operator in operators]
        geographies = repo.geographies_for_scoring()
        signals = repo.signals_for_operator_ids(operator_ids)
        people = repo.people_for_bundles()
        bundles = synthesize_bundles(
            operators=operators,
            geographies=geographies,
            signals=signals,
            people=people,
        )
        repo.replace_bundles(bundles)
        metrics.records_fetched = len(operators) + len(geographies) + len(signals) + len(people)
        metrics.records_persisted = (
            len(bundles)
            + sum(len(bundle["memberships"]) for bundle in bundles)
            + sum(len(bundle["top_people"]) for bundle in bundles)
        )
        return metrics
    finally:
        repo.close()


def synthesize_bundles(
    *,
    operators: Sequence[dict[str, Any]],
    geographies: Sequence[dict[str, Any]],
    signals: Sequence[dict[str, Any]],
    people: Sequence[dict[str, Any]],
    top_people_limit: int = 5,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    current_time = now or datetime.now(timezone.utc)
    geo_context = _geography_context(geographies)
    raw_candidates: list[dict[str, Any]] = []

    for definition in BUNDLE_TAXONOMY:
        memberships = _memberships_for_definition(definition, operators)
        if not memberships:
            continue
        member_ids = {str(membership["operator_id"]) for membership in memberships}
        member_signals = [
            signal for signal in signals if str(signal.get("related_operator_id")) in member_ids
        ]
        geography = _bundle_geography(memberships, geo_context)
        momentum = _momentum_components(memberships, member_signals, current_time)
        top_people = _top_people_for_bundle(
            memberships,
            people,
            definition=definition,
            limit=top_people_limit,
        )
        source_refs = _unique_refs(
            [
                BUNDLE_METHOD_REF,
                *_flatten_refs(membership["source_refs"] for membership in memberships),
                *_flatten_refs(signal.get("source_refs") for signal in member_signals),
                *_flatten_refs(entry.get("source_refs") for entry in geography["concentrations"]),
                *_flatten_refs(person["source_refs"] for person in top_people),
            ]
        )
        if not source_refs:
            continue
        source_confidence = _source_confidence(memberships, member_signals, geography)
        raw_candidates.append(
            {
                "definition": definition,
                "memberships": memberships,
                "member_ids": sorted(member_ids),
                "member_count": len(memberships),
                "geography": geography,
                "momentum": momentum,
                "supporting_signals": _supporting_signals(member_signals),
                "top_people": top_people,
                "source_refs": source_refs,
                "source_confidence": source_confidence,
                "raw_density": geography["bundle_density_per_10000_population"],
                "demand_proxy": geography["demand_proxy"],
                "momentum_index": momentum["momentum_index"],
            }
        )

    max_member_count = max((candidate["member_count"] for candidate in raw_candidates), default=1)
    max_density = max((candidate["raw_density"] for candidate in raw_candidates), default=0.0)
    max_momentum = max((candidate["momentum_index"] for candidate in raw_candidates), default=0.0)

    bundles = [
        _bundle_payload(
            candidate,
            max_member_count=max_member_count,
            max_density=max_density,
            max_momentum=max_momentum,
        )
        for candidate in raw_candidates
    ]
    return sorted(
        bundles,
        key=lambda bundle: (-float(bundle["bundle_score"]), str(bundle["label"]).lower()),
    )


def _memberships_for_definition(
    definition: BundleDefinition, operators: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    memberships: list[dict[str, Any]] = []
    for operator in operators:
        match_reasons = _match_operator(definition, operator)
        if match_reasons is None:
            continue
        source_refs = _unique_refs([*list(operator["source_refs"]), BUNDLE_METHOD_REF])
        memberships.append(
            {
                "operator_id": str(operator["id"]),
                "operator": operator,
                "match_reasons": match_reasons,
                "source_refs": source_refs,
                "confidence_score": _clamp(
                    float(operator["confidence_score"])
                    + 0.03 * len(match_reasons["category_matches"])
                    + 0.02 * len(match_reasons["tag_matches"])
                    + 0.01 * len(match_reasons["keyword_matches"])
                ),
            }
        )
    return sorted(
        memberships,
        key=lambda item: (
            -float(item["confidence_score"]),
            str(item["operator"]["name"]).lower(),
        ),
    )


def _match_operator(
    definition: BundleDefinition, operator: dict[str, Any]
) -> dict[str, Any] | None:
    categories = {str(category) for category in operator.get("categories") or []}
    raw_payloads = _raw_payloads(operator)
    tag_pairs = set(_raw_tag_pairs(raw_payloads))
    evidence_text = _operator_evidence_text(operator, raw_payloads, tag_pairs)
    category_matches = sorted(categories.intersection(definition.category_terms))
    tag_matches = sorted(tag_pairs.intersection(definition.tag_terms))
    keyword_matches = sorted(
        keyword for keyword in definition.keyword_terms if keyword in evidence_text
    )
    if not (category_matches or tag_matches or keyword_matches):
        return None
    return {
        "taxonomy_version": BUNDLE_METHOD_VERSION,
        "bundle_slug": definition.slug,
        "category_matches": category_matches,
        "tag_matches": tag_matches,
        "keyword_matches": keyword_matches,
        "description": definition.description,
    }


def _bundle_payload(
    candidate: dict[str, Any],
    *,
    max_member_count: int,
    max_density: float,
    max_momentum: float,
) -> dict[str, Any]:
    definition = candidate["definition"]
    member_scale = _log_normalize(float(candidate["member_count"]), float(max_member_count))
    low_supply_density = (
        _clamp(1 - float(candidate["raw_density"]) / max(max_density, 0.0001))
        if max_density > 0
        else 0.5
    )
    momentum = (
        _clamp(float(candidate["momentum_index"]) / max(max_momentum, 0.0001))
        if max_momentum > 0
        else 0.0
    )
    demand_proxy = round(float(candidate["demand_proxy"]), 4)
    member_scale_component = round(member_scale, 4)
    low_supply_density_component = round(low_supply_density, 4)
    momentum_component = round(momentum, 4)
    source_confidence = round(float(candidate["source_confidence"]), 4)
    components = {
        "demand_proxy": demand_proxy,
        "member_scale": member_scale_component,
        "low_supply_density": low_supply_density_component,
        "momentum": momentum_component,
        "source_confidence": source_confidence,
        "formula": BUNDLE_SCORE_FORMULA,
        "methodology_version": BUNDLE_METHOD_VERSION,
        "inputs": {
            "member_count": candidate["member_count"],
            "operator_ids": candidate["member_ids"],
            "bundle_density_per_10000_population": round(float(candidate["raw_density"]), 4),
            **candidate["momentum"],
        },
    }
    bundle_score = round(
        0.30 * demand_proxy
        + 0.20 * member_scale_component
        + 0.20 * low_supply_density_component
        + 0.20 * momentum_component
        + 0.10 * source_confidence,
        4,
    )
    return {
        "id": stable_id("bundle", definition.slug),
        "label": definition.label,
        "slug": slugify(definition.slug).replace("_", "-"),
        "bundle_score": bundle_score,
        "components": components,
        "geography": candidate["geography"],
        "member_count": candidate["member_count"],
        "memberships": candidate["memberships"],
        "top_people": candidate["top_people"],
        "supporting_signals": candidate["supporting_signals"],
        "source_refs": candidate["source_refs"],
        "confidence_score": round(float(candidate["source_confidence"]), 4),
    }


def _bundle_geography(
    memberships: Sequence[dict[str, Any]], geo_context: dict[str, Any]
) -> dict[str, Any]:
    operators = [membership["operator"] for membership in memberships]
    municipality_counts = Counter(
        _clean_text(operator.get("municipality")) for operator in operators
    )
    municipality_counts.pop(None, None)
    neighborhood_counts = Counter(
        (
            _clean_text(operator.get("municipality")),
            _clean_text(operator.get("neighborhood")),
        )
        for operator in operators
    )
    neighborhood_counts.pop((None, None), None)

    municipality_entries = [
        _geography_entry(
            geo_level="CSD",
            geo_name=municipality,
            municipality=municipality,
            count=count,
            geo=geo_context["csd_by_name"].get(_key(municipality)),
            fallback_refs=_refs_for_geo_group(operators, municipality, None),
        )
        for municipality, count in municipality_counts.items()
        if municipality
    ]
    neighborhood_entries = [
        _geography_entry(
            geo_level="neighborhood",
            geo_name=neighborhood,
            municipality=municipality,
            count=count,
            geo=geo_context["neighborhood_by_key"].get((_key(municipality), _key(neighborhood))),
            fallback_refs=_refs_for_geo_group(operators, municipality, neighborhood),
        )
        for (municipality, neighborhood), count in neighborhood_counts.items()
        if municipality and neighborhood
    ]
    concentrations = sorted(
        [*neighborhood_entries, *municipality_entries],
        key=lambda item: (
            -int(item["member_count"]),
            -float(item.get("density_per_10000_population") or 0.0),
            str(item["geo_name"]).lower(),
        ),
    )
    known_populations = [
        float(entry["population"])
        for entry in municipality_entries
        if entry.get("population") is not None
    ]
    total_population = sum(known_populations)
    bundle_density = len(memberships) / max(total_population / 10000, 1) if total_population else 0
    weighted_population = _weighted_average_population(municipality_entries)
    demand_proxy = _log_normalize(weighted_population, geo_context["max_population"])
    return {
        "municipalities": municipality_entries,
        "neighborhoods": neighborhood_entries,
        "concentrations": concentrations[:10],
        "bundle_density_per_10000_population": round(bundle_density, 4),
        "demand_proxy": round(demand_proxy, 4),
        "method": (
            "CSD and available neighborhood population denominators come from CM5 "
            "statcan_geography/statcan_denominator rows. Missing neighborhood "
            "denominators are reported as concentration counts and density falls "
            "back to the bundle's CSD population coverage."
        ),
        "source_quality": {
            "fixture_backed": any(_entry_fixture_backed(entry) for entry in concentrations),
        },
    }


def _geography_context(geographies: Sequence[dict[str, Any]]) -> dict[str, Any]:
    csd_by_name: dict[str, dict[str, Any]] = {}
    neighborhood_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    max_population = 1.0
    for geo in geographies:
        population = _optional_float(geo.get("population"))
        if population is not None:
            max_population = max(max_population, population)
        geo_level = str(geo.get("geo_level") or "")
        geo_name = str(geo.get("geo_name") or "")
        municipality = str(geo.get("municipality") or geo_name)
        if geo_level == "CSD":
            csd_by_name[_key(geo_name)] = geo
        elif geo_level == "neighborhood":
            neighborhood_by_key[(_key(municipality), _key(geo_name))] = geo
    return {
        "csd_by_name": csd_by_name,
        "neighborhood_by_key": neighborhood_by_key,
        "max_population": max_population,
    }


def _geography_entry(
    *,
    geo_level: str,
    geo_name: str,
    municipality: str,
    count: int,
    geo: dict[str, Any] | None,
    fallback_refs: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    population = _optional_float(geo.get("population") if geo else None)
    density = count / max(population / 10000, 1) if population is not None else None
    source_refs = _unique_refs(
        [
            *list(fallback_refs),
            *list((geo or {}).get("geography_source_refs") or []),
            *list((geo or {}).get("population_source_refs") or []),
        ]
    )
    confidence_score = _average(
        [
            _optional_float((geo or {}).get("geography_confidence")),
            _optional_float((geo or {}).get("population_confidence")),
        ],
        default=0.55,
    )
    population_payload = (geo or {}).get("population_payload") or {}
    demand_status = (
        str(population_payload.get("demand_source_status"))
        if isinstance(population_payload, dict)
        else None
    )
    return {
        "geo_level": geo_level,
        "geo_name": geo_name,
        "municipality": municipality,
        "member_count": count,
        "population": round(population, 4) if population is not None else None,
        "density_per_10000_population": round(density, 4) if density is not None else None,
        "population_denominator_id": (geo or {}).get("population_denominator_id"),
        "demand_source_status": demand_status,
        "confidence_score": round(confidence_score, 4),
        "source_refs": source_refs,
    }


def _refs_for_geo_group(
    operators: Sequence[dict[str, Any]], municipality: str | None, neighborhood: str | None
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for operator in operators:
        if municipality and _key(operator.get("municipality")) != _key(municipality):
            continue
        if neighborhood and _key(operator.get("neighborhood")) != _key(neighborhood):
            continue
        refs.extend(operator.get("source_refs") or [])
    return _unique_refs(refs)


def _momentum_components(
    memberships: Sequence[dict[str, Any]], signals: Sequence[dict[str, Any]], now: datetime
) -> dict[str, Any]:
    new_90 = 0
    new_180 = 0
    for membership in memberships:
        first_seen = _as_datetime(membership["operator"].get("first_seen_at"))
        if first_seen is None:
            continue
        if first_seen >= now - timedelta(days=90):
            new_90 += 1
        if first_seen >= now - timedelta(days=180):
            new_180 += 1
    signal_90 = 0
    signal_180 = 0
    for signal in signals:
        occurred_at = _as_datetime(signal.get("occurred_at"))
        if occurred_at is None:
            continue
        if occurred_at >= now - timedelta(days=90):
            signal_90 += 1
        if occurred_at >= now - timedelta(days=180):
            signal_180 += 1
    momentum_index = new_90 + 0.5 * new_180 + 0.5 * signal_90 + 0.25 * signal_180
    return {
        "new_members_90d": new_90,
        "new_members_180d": new_180,
        "signal_velocity_90d": signal_90,
        "signal_velocity_180d": signal_180,
        "momentum_index": round(momentum_index, 4),
    }


def _supporting_signals(signals: Sequence[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    ordered = sorted(
        signals,
        key=lambda signal: _as_datetime(signal.get("occurred_at")) or datetime.min.replace(
            tzinfo=timezone.utc
        ),
        reverse=True,
    )
    return [
        {
            "id": str(signal["id"]),
            "type": signal["type"],
            "severity": signal["severity"],
            "title": signal["title"],
            "occurred_at": _iso_or_none(signal.get("occurred_at")),
            "related_operator_id": signal.get("related_operator_id"),
            "confidence_score": float(signal["confidence_score"]),
            "source_refs": signal["source_refs"],
        }
        for signal in ordered[:limit]
        if signal.get("source_refs")
    ]


def _top_people_for_bundle(
    memberships: Sequence[dict[str, Any]],
    people: Sequence[dict[str, Any]],
    *,
    definition: BundleDefinition,
    limit: int,
) -> list[dict[str, Any]]:
    operators_by_name = {
        normalize_name(str(membership["operator"]["name"])): membership
        for membership in memberships
    }
    operators_by_org_id = {
        str(membership["operator"]["organization_id"]): membership
        for membership in memberships
        if membership["operator"].get("organization_id")
    }
    operators_by_org_name = {
        normalize_name(str(membership["operator"]["organization_name"])): membership
        for membership in memberships
        if membership["operator"].get("organization_name")
    }
    ranked: list[dict[str, Any]] = []
    for person in people:
        match = _person_bundle_match(
            person,
            operators_by_name=operators_by_name,
            operators_by_org_id=operators_by_org_id,
            operators_by_org_name=operators_by_org_name,
        )
        if match is None:
            continue
        membership, affiliation = match
        influence_score = _optional_float(person.get("influence_score"))
        source_refs = _unique_refs(
            [
                *list(person.get("source_refs") or []),
                *list(person.get("influence_source_refs") or []),
                *list(membership["source_refs"]),
            ]
        )
        if not source_refs:
            continue
        role = str(affiliation.get("role") or "public affiliation")
        affiliation_name = str(
            affiliation.get("organization_name") or membership["operator"]["name"]
        )
        score_text = (
            f"influence score {influence_score:.2f}"
            if influence_score is not None
            else "no influence score yet"
        )
        ranked.append(
            {
                "id": str(person["id"]),
                "name": str(person["name"]),
                "rank": 0,
                "roles": person.get("roles") or [],
                "primary_role": (person.get("roles") or [None])[0],
                "primary_affiliation": affiliation_name,
                "influence_score": influence_score,
                "why_appears": (
                    f"{role} at {affiliation_name} links this person to "
                    f"{definition.label}; {score_text}."
                ),
                "source_refs": source_refs,
                "confidence_score": min(
                    float(person.get("confidence_score") or 0.5),
                    float(membership["confidence_score"]),
                ),
            }
        )
    ranked.sort(
        key=lambda person: (
            -(person["influence_score"] if person["influence_score"] is not None else 0.0),
            str(person["name"]).lower(),
        )
    )
    for index, person in enumerate(ranked[:limit], start=1):
        person["rank"] = index
    return ranked[:limit]


def _person_bundle_match(
    person: dict[str, Any],
    *,
    operators_by_name: dict[str, dict[str, Any]],
    operators_by_org_id: dict[str, dict[str, Any]],
    operators_by_org_name: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    for affiliation in person.get("affiliations") or []:
        if not isinstance(affiliation, dict):
            continue
        organization_id = str(affiliation.get("organization_id") or "")
        if organization_id and organization_id in operators_by_org_id:
            return operators_by_org_id[organization_id], affiliation
        affiliation_name = normalize_name(str(affiliation.get("organization_name") or ""))
        if not affiliation_name:
            continue
        if affiliation_name in operators_by_name:
            return operators_by_name[affiliation_name], affiliation
        if affiliation_name in operators_by_org_name:
            return operators_by_org_name[affiliation_name], affiliation
    return None


def _source_confidence(
    memberships: Sequence[dict[str, Any]],
    signals: Sequence[dict[str, Any]],
    geography: dict[str, Any],
) -> float:
    confidences = [
        *[float(membership["confidence_score"]) for membership in memberships],
        *[float(signal["confidence_score"]) for signal in signals],
        *[float(entry["confidence_score"]) for entry in geography["concentrations"]],
    ]
    base = _average(confidences, default=0.5)
    if geography["source_quality"]["fixture_backed"]:
        base *= 0.9
    return _clamp(base)


def _operator_evidence_text(
    operator: dict[str, Any],
    raw_payloads: Sequence[dict[str, Any]],
    tag_pairs: Iterable[str],
) -> str:
    values = [
        str(operator.get("name") or ""),
        " ".join(str(category) for category in operator.get("categories") or []),
        " ".join(tag_pairs),
    ]
    for raw in raw_payloads:
        values.extend(str(raw.get(field) or "") for field in RAW_TEXT_FIELDS)
        tags = raw.get("tags")
        if isinstance(tags, dict):
            values.extend(str(value) for value in tags.values() if value)
    return normalize_name(" ".join(values))


def _raw_payloads(operator: dict[str, Any]) -> list[dict[str, Any]]:
    payloads = operator.get("raw_payloads") or []
    if not isinstance(payloads, list):
        return []
    return [payload for payload in payloads if isinstance(payload, dict)]


def _raw_tag_pairs(raw_payloads: Sequence[dict[str, Any]]) -> list[str]:
    pairs: set[str] = set()
    for raw in raw_payloads:
        tags = raw.get("tags")
        if isinstance(tags, dict):
            for key in OSM_SUBTYPE_TAG_KEYS:
                value = tags.get(key)
                if value:
                    pairs.add(f"{_key(key)}={_key(value)}")
        for key in RAW_TEXT_FIELDS:
            value = raw.get(key)
            if value:
                pairs.add(f"{_key(key)}={_key(value)}")
    return sorted(pairs)


def _weighted_average_population(entries: Sequence[dict[str, Any]]) -> float:
    weighted_sum = 0.0
    total_count = 0
    for entry in entries:
        population = _optional_float(entry.get("population"))
        if population is None:
            continue
        count = int(entry["member_count"])
        weighted_sum += population * count
        total_count += count
    return weighted_sum / total_count if total_count else 0.0


def _entry_fixture_backed(entry: dict[str, Any]) -> bool:
    status = str(entry.get("demand_source_status") or "").lower()
    return "fixture" in status


def _log_normalize(value: float, ceiling: float) -> float:
    if value <= 0 or ceiling <= 0:
        return 0.0
    return _clamp(math.log1p(value) / math.log1p(ceiling))


def _average(values: Iterable[float | None], *, default: float) -> float:
    cleaned = [value for value in values if value is not None]
    if not cleaned:
        return default
    return sum(cleaned) / len(cleaned)


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, int | float | str | Decimal):
        return float(value)
    return None


def _as_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    return None


def _iso_or_none(value: object) -> str | None:
    parsed = _as_datetime(value)
    if parsed is None:
        return None
    return parsed.isoformat()


def _clean_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _key(value: object) -> str:
    return normalize_name(str(value or ""))


def _flatten_refs(ref_groups: Iterable[Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for group in ref_groups:
        if isinstance(group, list):
            refs.extend(ref for ref in group if isinstance(ref, dict))
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


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
