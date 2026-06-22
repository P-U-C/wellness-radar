from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Protocol, cast

import httpx
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from apps.api.app.config import settings
from packages.shared.ids import stable_id

BRIEF_CONDITION = "daily_market_brief"
DEFAULT_WINDOW_HOURS = 72
DEFAULT_MOVEMENT_THRESHOLD = 0.05
DEFAULT_MAX_SECTION_ITEMS = 8
DETERMINISTIC_NARRATIVE_MODEL = "deterministic-template-v1"
DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-5"

LEAD_WEDGE_CATEGORIES = [
    "recovery_contrast_therapy",
    "spa_thermal",
    "community_social_wellness",
]

CATEGORY_LABELS = {
    "recovery_contrast_therapy": "recovery and contrast therapy",
    "fitness_movement": "fitness and movement",
    "mind_meditation": "mind and meditation",
    "spa_thermal": "spa and thermal",
    "nutrition_longevity": "nutrition and longevity",
    "allied_health": "allied health",
    "womens_health": "women's health",
    "preventive_diagnostic": "preventive and diagnostic",
    "mental_health": "mental health",
    "community_social_wellness": "community and social wellness",
    "wellness_retail_product": "wellness retail and product",
}

SECTION_ORDER = [
    "changed_operators",
    "new_signals",
    "opportunity_movement",
    "new_reachable_leads",
]


@dataclass(frozen=True)
class BriefGenerationResult:
    brief_id: str
    brief_date: date
    generated_at: datetime
    window_start: datetime
    window_end: datetime
    status: str
    brief_text: str
    sections: dict[str, list[dict[str, Any]]]
    top_actions: list[dict[str, Any]]
    counts: dict[str, Any]
    source_refs: list[dict[str, Any]]
    narrative_model: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.brief_id,
            "brief_date": self.brief_date.isoformat(),
            "generated_at": self.generated_at.isoformat(),
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "status": self.status,
            "brief_text": self.brief_text,
            "sections": self.sections,
            "top_actions": self.top_actions,
            "counts": self.counts,
            "source_refs": self.source_refs,
            "narrative_model": self.narrative_model,
        }


class BriefNarrativeBuilder(Protocol):
    model_name: str

    def build(self, brief_payload: dict[str, Any], deterministic_text: str) -> str:
        ...


class DeterministicBriefNarrativeBuilder:
    model_name = DETERMINISTIC_NARRATIVE_MODEL

    def build(self, brief_payload: dict[str, Any], deterministic_text: str) -> str:
        return deterministic_text


class ClaudeBriefNarrativeBuilder:
    def __init__(
        self,
        api_key: str,
        *,
        model_name: str = DEFAULT_CLAUDE_MODEL,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.client = client or httpx.Client(timeout=45.0)

    def build(self, brief_payload: dict[str, Any], deterministic_text: str) -> str:
        prompt_payload = {
            "deterministic_text": deterministic_text,
            "brief": {
                "brief_date": brief_payload["brief_date"],
                "status": brief_payload["status"],
                "sections": brief_payload["sections"],
                "top_actions": brief_payload["top_actions"],
                "counts": brief_payload["counts"],
            },
        }
        response = self.client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model_name,
                "max_tokens": 900,
                "temperature": 0,
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Rewrite the supplied daily market brief in concise reader-facing "
                            "prose. Use only supplied fields. Do not add facts, numbers, names, "
                            "recommendations, medical advice, or source claims. Return plain text "
                            "only.\n\n"
                            f"{json.dumps(prompt_payload, sort_keys=True, default=str)}"
                        ),
                    }
                ],
            },
        )
        response.raise_for_status()
        text = _anthropic_text(response.json()).strip()
        return text or deterministic_text


def narrative_builder_from_env() -> BriefNarrativeBuilder:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return DeterministicBriefNarrativeBuilder()
    return ClaudeBriefNarrativeBuilder(
        api_key,
        model_name=os.getenv("ANTHROPIC_MODEL", DEFAULT_CLAUDE_MODEL),
    )


def generate_daily_brief(
    *,
    database_url: str | None = None,
    brief_date: date | None = None,
    window_hours: int | None = None,
    movement_threshold: float | None = None,
    max_section_items: int = DEFAULT_MAX_SECTION_ITEMS,
    narrative_builder: BriefNarrativeBuilder | None = None,
) -> BriefGenerationResult:
    active_date = brief_date or datetime.now(timezone.utc).date()
    active_window_hours = window_hours or _env_int("WR_BRIEF_WINDOW_HOURS", DEFAULT_WINDOW_HOURS)
    active_threshold = movement_threshold or _env_float(
        "WR_BRIEF_MOVEMENT_THRESHOLD",
        DEFAULT_MOVEMENT_THRESHOLD,
    )
    window_end = datetime.now(timezone.utc)

    with psycopg.connect(database_url or settings.database_url, row_factory=dict_row) as conn:
        previous_brief = _latest_brief(conn)
        window_start = (
            _ensure_aware(cast(datetime, previous_brief["generated_at"]))
            if previous_brief
            else window_end - timedelta(hours=active_window_hours)
        )
        had_score_snapshot = _has_score_snapshot(conn)
        sections = {
            "changed_operators": _changed_operators(conn, window_start, max_section_items),
            "new_signals": _new_high_trust_signals(conn, window_start, max_section_items),
            "opportunity_movement": _opportunity_movement(
                conn,
                active_date,
                window_end,
                had_score_snapshot=had_score_snapshot,
                threshold=active_threshold,
                limit=max_section_items,
            ),
            "new_reachable_leads": _new_reachable_leads(conn, window_start, max_section_items),
        }
        _assert_source_backed_sections(sections)
        top_propositions = _top_propositions(conn, max_section_items)
        top_actions = _top_actions(sections, top_propositions=top_propositions)
        _assert_source_backed_actions(top_actions)
        counts = {
            "changed_operators": len(sections["changed_operators"]),
            "new_signals": len(sections["new_signals"]),
            "opportunity_movement": len(sections["opportunity_movement"]),
            "new_reachable_leads": len(sections["new_reachable_leads"]),
            "top_propositions": len(top_propositions),
            "top_actions": len(top_actions),
            "window_hours": round((window_end - window_start).total_seconds() / 3600, 3),
            "had_prior_brief": previous_brief is not None,
            "had_prior_opportunity_snapshot": had_score_snapshot,
        }
        status = _brief_status(counts, had_score_snapshot)
        source_refs = _dedupe_refs(
            [
                *[
                    ref
                    for section_items in sections.values()
                    for item in section_items
                    for ref in item["source_refs"]
                ],
                *[ref for action in top_actions for ref in action["source_refs"]],
            ]
        )

        brief_id = stable_id("daily_brief", active_date.isoformat())
        deterministic_payload: dict[str, Any] = {
            "id": brief_id,
            "brief_date": active_date.isoformat(),
            "generated_at": window_end.isoformat(),
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "status": status,
            "sections": sections,
            "top_actions": top_actions,
            "counts": counts,
            "source_refs": source_refs,
        }
        deterministic_text = build_deterministic_brief_text(deterministic_payload)
        builder = narrative_builder or narrative_builder_from_env()
        brief_text = _build_narrative(builder, deterministic_payload, deterministic_text)
        narrative_model = (
            builder.model_name
            if brief_text != deterministic_text
            else DETERMINISTIC_NARRATIVE_MODEL
        )
        result = BriefGenerationResult(
            brief_id=brief_id,
            brief_date=active_date,
            generated_at=window_end,
            window_start=window_start,
            window_end=window_end,
            status=status,
            brief_text=brief_text,
            sections=sections,
            top_actions=top_actions,
            counts=counts,
            source_refs=source_refs,
            narrative_model=narrative_model,
        )
        _persist_brief(conn, result)
        _snapshot_current_scores(conn, active_date)
        conn.commit()
        return result


def build_deterministic_brief_text(brief_payload: dict[str, Any]) -> str:
    counts = brief_payload["counts"]
    actions = brief_payload["top_actions"]
    sections = brief_payload["sections"]
    lines = [
        f"Daily Market Brief - {brief_payload['brief_date']}",
        (
            f"Window: {_compact_dt(brief_payload['window_start'])} to "
            f"{_compact_dt(brief_payload['window_end'])} UTC."
        ),
    ]
    if brief_payload["status"] == "initial_snapshot":
        lines.append(
            "Initial snapshot: opportunity movement needs a prior analytics run; this brief "
            "sets the comparison baseline."
        )
    elif brief_payload["status"] == "no_material_changes":
        lines.append(
            "No material source-backed market changes were detected in the comparison window."
        )
    else:
        lines.append(
            "Material source-backed changes were detected across "
            f"{_changed_section_count(counts)} brief section(s)."
        )

    if actions:
        lines.append("")
        lines.append("Top actions:")
        for index, action in enumerate(actions[:3], start=1):
            lines.append(f"{index}. {action['title']} - {action['summary']}")
    else:
        lines.append("")
        lines.append("Top actions: none today; keep the existing watchlist cadence.")

    lines.append("")
    lines.append("Change counts:")
    lines.append(f"- Changed operators: {counts['changed_operators']}")
    lines.append(f"- New high-trust signals: {counts['new_signals']}")
    lines.append(f"- Opportunity movements: {counts['opportunity_movement']}")
    lines.append(f"- New reachable leads: {counts['new_reachable_leads']}")

    for section_key in SECTION_ORDER:
        items = sections[section_key]
        if not items:
            continue
        lines.append("")
        lines.append(f"{_section_label(section_key)}:")
        for item in items[:5]:
            lines.append(f"- {item['title']} - {item['summary']}")
    return "\n".join(lines)


def _latest_brief(conn: Any) -> dict[str, Any] | None:
    return cast(
        dict[str, Any] | None,
        conn.execute(
            """
            SELECT id, generated_at
            FROM daily_brief
            ORDER BY generated_at DESC
            LIMIT 1
            """
        ).fetchone(),
    )


def _has_score_snapshot(conn: Any) -> bool:
    row = conn.execute(
        "SELECT EXISTS (SELECT 1 FROM opportunity_score_snapshot) AS has_rows"
    ).fetchone()
    return bool(row["has_rows"])


def _changed_operators(conn: Any, window_start: datetime, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          id,
          name,
          categories,
          status::text AS status,
          address,
          municipality,
          neighborhood,
          licence_ref,
          source_refs,
          confidence_score,
          first_seen_at,
          last_seen_at
        FROM "operator"
        WHERE jsonb_array_length(source_refs) > 0
          AND (
            first_seen_at >= %s
            OR (status = 'planned'::operator_status AND last_seen_at >= %s)
          )
          AND (categories && %s::text[] OR status = 'planned'::operator_status)
        ORDER BY
          CASE WHEN status = 'planned'::operator_status THEN 0 ELSE 1 END,
          first_seen_at DESC,
          confidence_score DESC,
          name ASC
        LIMIT %s
        """,
        (window_start, window_start, LEAD_WEDGE_CATEGORIES, limit),
    ).fetchall()
    items = []
    for row in rows:
        categories = list(row["categories"] or [])
        category = categories[0] if categories else "wellness"
        location = _location(row)
        status = str(row["status"])
        title = (
            f"Planned operator: {row['name']}"
            if status == "planned"
            else f"New operator: {row['name']}"
        )
        summary = (
            f"{_category_label(category)} operator surfaced in {location}; "
            f"status is {status}."
        )
        items.append(
            {
                "id": stable_id("brief_operator", row["id"]),
                "item_type": "operator",
                "operator_id": row["id"],
                "title": title,
                "summary": summary,
                "name": row["name"],
                "categories": categories,
                "primary_category": category,
                "status": status,
                "municipality": row["municipality"],
                "neighborhood": row["neighborhood"],
                "address": row["address"],
                "licence_ref": row["licence_ref"],
                "first_seen_at": _iso(row["first_seen_at"]),
                "source_refs": _as_refs(row["source_refs"]),
                "confidence_score": float(row["confidence_score"]),
            }
        )
    return items


def _new_high_trust_signals(
    conn: Any,
    window_start: datetime,
    limit: int,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          id,
          type,
          severity::text AS severity,
          title,
          summary,
          source_name,
          source_url,
          trust_tier::text AS trust_tier,
          occurred_at,
          ingested_at,
          related_operator_id,
          source_refs,
          confidence_score
        FROM signal
        WHERE jsonb_array_length(source_refs) > 0
          AND ingested_at >= %s
          AND (
            severity = 'high'::signal_severity
            OR trust_tier IN ('official', 'reputable_press')
          )
        ORDER BY
          CASE severity WHEN 'high' THEN 0 WHEN 'notable' THEN 1 ELSE 2 END,
          CASE trust_tier WHEN 'official' THEN 0 WHEN 'reputable_press' THEN 1 ELSE 2 END,
          occurred_at DESC,
          ingested_at DESC
        LIMIT %s
        """,
        (window_start, limit),
    ).fetchall()
    items = []
    for row in rows:
        signal_type = str(row["type"]).replace("_", " ")
        summary = row["summary"] or f"{signal_type.title()} signal from {row['source_name']}."
        items.append(
            {
                "id": stable_id("brief_signal", row["id"]),
                "item_type": "signal",
                "signal_id": row["id"],
                "title": str(row["title"]),
                "summary": summary,
                "signal_type": row["type"],
                "severity": row["severity"],
                "source_name": row["source_name"],
                "source_url": row["source_url"],
                "trust_tier": row["trust_tier"],
                "occurred_at": _iso(row["occurred_at"]),
                "ingested_at": _iso(row["ingested_at"]),
                "related_operator_id": row["related_operator_id"],
                "source_refs": _as_refs(row["source_refs"]),
                "confidence_score": float(row["confidence_score"]),
            }
        )
    return items


def _opportunity_movement(
    conn: Any,
    brief_date: date,
    window_end: datetime,
    *,
    had_score_snapshot: bool,
    threshold: float,
    limit: int,
) -> list[dict[str, Any]]:
    if not had_score_snapshot:
        return []
    rows = conn.execute(
        """
        WITH previous AS (
          SELECT DISTINCT ON (scorecard_id)
            scorecard_id,
            opportunity_score AS previous_score,
            captured_at AS previous_captured_at
          FROM opportunity_score_snapshot
          WHERE captured_at < %s
          ORDER BY scorecard_id, captured_at DESC
        ),
        ranked AS (
          SELECT
            sc.id,
            sc.category,
            sc.geo_code,
            sc.geo_name,
            sc.opportunity_score,
            sc.source_refs,
            sc.confidence_score,
            sc.calculation_method,
            sc.generated_at,
            previous.previous_score,
            previous.previous_captured_at,
            row_number() OVER (
              ORDER BY sc.opportunity_score DESC, sc.geo_name ASC, sc.category ASC
            ) AS current_rank
          FROM opportunity_scorecard sc
          LEFT JOIN previous ON previous.scorecard_id = sc.id
          WHERE jsonb_array_length(sc.source_refs) > 0
        )
        SELECT *
        FROM ranked
        WHERE (
          previous_score IS NULL
          AND current_rank <= 3
        )
        OR abs(opportunity_score - previous_score) >= %s
        ORDER BY
          CASE WHEN previous_score IS NULL THEN 1 ELSE 0 END,
          (opportunity_score - COALESCE(previous_score, 0)) DESC,
          opportunity_score DESC,
          geo_name ASC
        LIMIT %s
        """,
        (window_end, threshold, limit),
    ).fetchall()
    items = []
    for row in rows:
        previous_score = (
            float(row["previous_score"]) if row["previous_score"] is not None else None
        )
        current_score = float(row["opportunity_score"])
        delta = None if previous_score is None else round(current_score - previous_score, 4)
        movement_label = "newly top-ranked" if previous_score is None else _movement_label(delta)
        summary = (
            f"{_category_label(row['category'])} in {row['geo_name']} is {movement_label} "
            f"at {current_score:.2f}"
        )
        if delta is not None:
            summary += f" ({delta:+.2f} vs prior snapshot)"
        summary += "."
        items.append(
            {
                "id": stable_id("brief_opportunity", brief_date.isoformat(), row["id"]),
                "item_type": "opportunity_scorecard",
                "scorecard_id": row["id"],
                "title": f"{row['geo_name']} {_category_label(row['category'])} gap",
                "summary": summary,
                "category": row["category"],
                "geo_code": row["geo_code"],
                "geo_name": row["geo_name"],
                "opportunity_score": current_score,
                "previous_score": previous_score,
                "delta": delta,
                "movement": movement_label,
                "current_rank": int(row["current_rank"]),
                "generated_at": _iso(row["generated_at"]),
                "previous_captured_at": _iso_or_none(row["previous_captured_at"]),
                "source_refs": _as_refs(row["source_refs"]),
                "confidence_score": float(row["confidence_score"]),
                "calculation_method": row["calculation_method"],
            }
        )
    return items


def _new_reachable_leads(conn: Any, window_start: datetime, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          op.id,
          op.name,
          op.categories,
          op.status::text AS status,
          op.address,
          op.municipality,
          op.neighborhood,
          op.source_refs AS operator_source_refs,
          op.confidence_score AS operator_confidence,
          min(oc.first_seen_at) AS contact_first_seen_at,
          count(oc.id)::int AS contact_count,
          array_agg(DISTINCT oc.contact_type ORDER BY oc.contact_type) AS contact_types,
          jsonb_agg(DISTINCT oc.source_ref) AS contact_source_refs
        FROM operator_contact oc
        JOIN "operator" op ON op.id = oc.operator_id
        WHERE oc.first_seen_at >= %s
          AND jsonb_array_length(op.source_refs) > 0
          AND oc.source_ref ? 'source_name'
        GROUP BY
          op.id,
          op.name,
          op.categories,
          op.status,
          op.address,
          op.municipality,
          op.neighborhood,
          op.source_refs,
          op.confidence_score
        ORDER BY
          contact_count DESC,
          contact_first_seen_at DESC,
          op.name ASC
        LIMIT %s
        """,
        (window_start, limit),
    ).fetchall()
    items = []
    for row in rows:
        contact_types = [str(item) for item in row["contact_types"] or []]
        source_refs = _dedupe_refs(
            [
                *_as_refs(row["contact_source_refs"]),
                *_as_refs(row["operator_source_refs"]),
            ]
        )
        contact_label = ", ".join(contact_types) if contact_types else "contact"
        items.append(
            {
                "id": stable_id("brief_lead", row["id"]),
                "item_type": "lead",
                "operator_id": row["id"],
                "title": f"New reachable lead: {row['name']}",
                "summary": (
                    f"{row['name']} gained public {contact_label} data "
                    f"({int(row['contact_count'])} contact row(s))."
                ),
                "name": row["name"],
                "categories": list(row["categories"] or []),
                "status": row["status"],
                "municipality": row["municipality"],
                "neighborhood": row["neighborhood"],
                "address": row["address"],
                "contact_types": contact_types,
                "contact_count": int(row["contact_count"]),
                "contact_first_seen_at": _iso(row["contact_first_seen_at"]),
                "source_refs": source_refs,
                "confidence_score": float(row["operator_confidence"]),
            }
        )
    return items


def _top_propositions(conn: Any, limit: int) -> list[dict[str, Any]]:
    table_row = conn.execute(
        "SELECT to_regclass('opportunity_proposition') AS relation_name"
    ).fetchone()
    if not table_row or not table_row["relation_name"]:
        return []
    rows = conn.execute(
        """
        SELECT
          id,
          headline,
          summary,
          category,
          geo_name,
          geo_level,
          municipality,
          competitor_count_within_radius,
          competitor_radius_km,
          population,
          business_count,
          demand_source,
          opportunity_score,
          confidence_score,
          source_refs,
          generated_at
        FROM opportunity_proposition
        WHERE jsonb_array_length(source_refs) > 0
        ORDER BY
          CASE WHEN geo_level = 'neighborhood' THEN 0 ELSE 1 END,
          opportunity_score DESC,
          confidence_score DESC,
          geo_name ASC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()
    return [
        {
            "id": stable_id("brief_proposition", row["id"]),
            "item_type": "opportunity_proposition",
            "proposition_id": row["id"],
            "title": row["headline"],
            "summary": row["summary"],
            "category": row["category"],
            "geo_name": row["geo_name"],
            "geo_level": row["geo_level"],
            "municipality": row["municipality"],
            "competitor_count_within_radius": int(row["competitor_count_within_radius"]),
            "competitor_radius_km": float(row["competitor_radius_km"]),
            "population": float(row["population"]) if row["population"] is not None else None,
            "business_count": (
                float(row["business_count"]) if row["business_count"] is not None else None
            ),
            "demand_source": row["demand_source"],
            "opportunity_score": float(row["opportunity_score"]),
            "generated_at": _iso(row["generated_at"]),
            "source_refs": _as_refs(row["source_refs"]),
            "confidence_score": float(row["confidence_score"]),
        }
        for row in rows
    ]


def _top_actions(
    sections: dict[str, list[dict[str, Any]]],
    *,
    top_propositions: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    candidates: list[tuple[float, dict[str, Any]]] = []
    leads = sections["new_reachable_leads"]
    operators = sections["changed_operators"]
    signals = sections["new_signals"]
    movements = sections["opportunity_movement"]
    propositions = top_propositions or []

    for proposition in propositions:
        evidence = [_evidence("top_propositions", proposition)]
        title = f"Evaluate proposition: {proposition['title']}"
        summary = proposition["summary"]
        score = 125 + float(proposition.get("opportunity_score") or 0)
        candidates.append((score, _action("proposition", title, summary, evidence)))

    for movement in movements:
        matching_leads = [
            lead
            for lead in leads
            if _same_geo(lead.get("municipality"), movement.get("geo_name"))
            and movement.get("category") in (lead.get("categories") or [])
        ]
        delta = float(movement.get("delta") or 0)
        if matching_leads:
            evidence = [
                _evidence("opportunity_movement", movement),
                *[_evidence("new_reachable_leads", lead) for lead in matching_leads[:3]],
            ]
            title = f"Scout {movement['geo_name']} for {_category_label(movement['category'])}"
            summary = (
                f"Opportunity score is {movement['movement']} and "
                f"{len(matching_leads)} newly reachable lead(s) appeared."
            )
            candidates.append((120 + delta, _action("scout", title, summary, evidence)))
        else:
            evidence = [_evidence("opportunity_movement", movement)]
            title = f"Review {movement['geo_name']} {_category_label(movement['category'])} gap"
            summary = movement["summary"]
            candidates.append((85 + delta, _action("review_gap", title, summary, evidence)))

    for operator in operators:
        evidence = [_evidence("changed_operators", operator)]
        is_planned = operator.get("status") == "planned"
        title = (
            f"Track planned opening: {operator['name']}"
            if is_planned
            else f"Map new competitor: {operator['name']}"
        )
        summary = operator["summary"]
        candidates.append((95 if is_planned else 68, _action("operator", title, summary, evidence)))

    for signal in signals:
        evidence = [_evidence("new_signals", signal)]
        severity_score = 90 if signal.get("severity") == "high" else 72
        trust_score = 8 if signal.get("trust_tier") == "official" else 3
        title = f"Review {str(signal['signal_type']).replace('_', ' ')} signal"
        summary = f"{signal['title']}: {signal['summary']}"
        candidates.append(
            (severity_score + trust_score, _action("signal", title, summary, evidence))
        )

    for lead in leads:
        evidence = [_evidence("new_reachable_leads", lead)]
        title = f"Prioritize outreach: {lead['name']}"
        summary = (
            f"Public {', '.join(lead['contact_types']) or 'contact'} data is now available."
        )
        candidates.append(
            (
                62 + int(lead.get("contact_count") or 0),
                _action("lead", title, summary, evidence),
            )
        )

    unique: dict[str, tuple[float, dict[str, Any]]] = {}
    for score, action in candidates:
        key = str(action["title"]).lower()
        if key not in unique or score > unique[key][0]:
            unique[key] = (score, action)
    ordered = sorted(unique.values(), key=lambda item: (-item[0], item[1]["title"]))
    return [action for _, action in ordered[:3]]


def _action(
    kind: str,
    title: str,
    summary: str,
    evidence_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    source_refs = _dedupe_refs(
        [ref for row in evidence_rows for ref in row.get("source_refs", [])]
    )
    return {
        "id": stable_id("brief_action", kind, title),
        "title": title,
        "summary": summary,
        "action_type": kind,
        "evidence_rows": evidence_rows,
        "source_refs": source_refs,
    }


def _evidence(section: str, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "section": section,
        "item_id": item["id"],
        "title": item["title"],
        "source_refs": item["source_refs"],
    }


def _persist_brief(conn: Any, result: BriefGenerationResult) -> None:
    conn.execute(
        """
        INSERT INTO daily_brief (
          id,
          brief_date,
          generated_at,
          window_start,
          window_end,
          status,
          brief_text,
          sections,
          top_actions,
          counts,
          source_refs,
          narrative_model
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (brief_date) DO UPDATE SET
          generated_at = EXCLUDED.generated_at,
          window_start = EXCLUDED.window_start,
          window_end = EXCLUDED.window_end,
          status = EXCLUDED.status,
          brief_text = EXCLUDED.brief_text,
          sections = EXCLUDED.sections,
          top_actions = EXCLUDED.top_actions,
          counts = EXCLUDED.counts,
          source_refs = EXCLUDED.source_refs,
          narrative_model = EXCLUDED.narrative_model,
          updated_at = now()
        """,
        (
            result.brief_id,
            result.brief_date,
            result.generated_at,
            result.window_start,
            result.window_end,
            result.status,
            result.brief_text,
            Jsonb(result.sections),
            Jsonb(result.top_actions),
            Jsonb(result.counts),
            Jsonb(result.source_refs),
            result.narrative_model,
        ),
    )


def _snapshot_current_scores(conn: Any, brief_date: date) -> None:
    rows = conn.execute(
        """
        SELECT
          id,
          category,
          geo_code,
          geo_name,
          geo_level,
          opportunity_score,
          source_refs,
          confidence_score,
          calculation_method
        FROM opportunity_scorecard
        WHERE jsonb_array_length(source_refs) > 0
        """
    ).fetchall()
    for row in rows:
        conn.execute(
            """
            INSERT INTO opportunity_score_snapshot (
              id,
              brief_date,
              scorecard_id,
              category,
              geo_code,
              geo_name,
              geo_level,
              opportunity_score,
              source_refs,
              confidence_score,
              calculation_method,
              captured_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (brief_date, scorecard_id) DO UPDATE SET
              category = EXCLUDED.category,
              geo_code = EXCLUDED.geo_code,
              geo_name = EXCLUDED.geo_name,
              geo_level = EXCLUDED.geo_level,
              opportunity_score = EXCLUDED.opportunity_score,
              source_refs = EXCLUDED.source_refs,
              confidence_score = EXCLUDED.confidence_score,
              calculation_method = EXCLUDED.calculation_method,
              captured_at = now()
            """,
            (
                stable_id("opp_snapshot", brief_date.isoformat(), row["id"]),
                brief_date,
                row["id"],
                row["category"],
                row["geo_code"],
                row["geo_name"],
                row["geo_level"],
                row["opportunity_score"],
                Jsonb(_as_refs(row["source_refs"])),
                row["confidence_score"],
                row["calculation_method"],
            ),
        )


def _brief_status(counts: dict[str, Any], had_score_snapshot: bool) -> str:
    material_count = (
        int(counts["changed_operators"])
        + int(counts["new_signals"])
        + int(counts["opportunity_movement"])
        + int(counts["new_reachable_leads"])
    )
    if not had_score_snapshot:
        return "initial_snapshot"
    return "material_changes" if material_count else "no_material_changes"


def _assert_source_backed_sections(sections: dict[str, list[dict[str, Any]]]) -> None:
    for section, items in sections.items():
        for item in items:
            if not item.get("source_refs"):
                raise ValueError(f"brief item {section}/{item.get('id')} is missing source_refs")


def _assert_source_backed_actions(actions: list[dict[str, Any]]) -> None:
    for action in actions:
        if not action.get("source_refs"):
            raise ValueError(f"brief action {action.get('id')} is missing source_refs")


def _build_narrative(
    builder: BriefNarrativeBuilder,
    brief_payload: dict[str, Any],
    deterministic_text: str,
) -> str:
    if isinstance(builder, DeterministicBriefNarrativeBuilder):
        return deterministic_text
    try:
        return builder.build(brief_payload, deterministic_text)
    except Exception:
        return deterministic_text


def _anthropic_text(body: dict[str, Any]) -> str:
    for chunk in body.get("content") or []:
        if chunk.get("type") == "text" and chunk.get("text"):
            return str(chunk["text"])
    raise ValueError("Claude response did not include text content")


def _changed_section_count(counts: dict[str, Any]) -> int:
    return sum(1 for key in SECTION_ORDER if int(counts[key]) > 0)


def _section_label(section_key: str) -> str:
    return {
        "changed_operators": "Changed operators",
        "new_signals": "New high-trust signals",
        "opportunity_movement": "Opportunity movement",
        "new_reachable_leads": "New reachable leads",
    }[section_key]


def _category_label(category: Any) -> str:
    return CATEGORY_LABELS.get(str(category), str(category).replace("_", " "))


def _location(row: dict[str, Any]) -> str:
    return (
        str(
            row.get("neighborhood")
            or row.get("municipality")
            or row.get("address")
            or "Metro Vancouver"
        )
    )


def _same_geo(left: Any, right: Any) -> bool:
    return bool(left and right and str(left).strip().lower() == str(right).strip().lower())


def _movement_label(delta: float | None) -> str:
    if delta is None:
        return "newly top-ranked"
    if delta > 0:
        return "rising"
    if delta < 0:
        return "falling"
    return "unchanged"


def _as_refs(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [dict(value)]
    return []


def _dedupe_refs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for ref in refs:
        if not ref or not ref.get("source_name"):
            continue
        key = json.dumps(ref, sort_keys=True, default=str)
        deduped[key] = ref
    return list(deduped.values())


def _compact_dt(value: Any) -> str:
    text = str(value)
    return text.replace("+00:00", "Z").replace("T", " ")[:16]


def _iso(value: Any) -> str:
    if isinstance(value, datetime):
        return _ensure_aware(value).isoformat()
    return str(value)


def _iso_or_none(value: Any) -> str | None:
    return None if value is None else _iso(value)


def _ensure_aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _env_int(key: str, default: int) -> int:
    value = os.getenv(key)
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _env_float(key: str, default: float) -> float:
    value = os.getenv(key)
    if not value:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default
