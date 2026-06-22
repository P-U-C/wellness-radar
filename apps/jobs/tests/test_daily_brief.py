from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from apps.jobs.analytics.daily_brief import (
    _assert_source_backed_sections,
    _top_actions,
    _window_start,
    build_deterministic_brief_text,
)

SOURCE_REF = {
    "source_name": "fixture",
    "url": "https://example.test/source",
    "trust_tier": "official",
    "seen_at": "2026-06-22T00:00:00Z",
    "source_record_id": "record-1",
    "licence": "fixture",
}


def test_top_actions_cite_source_backed_evidence_rows() -> None:
    sections: dict[str, list[dict[str, Any]]] = {
        "changed_operators": [
            {
                "id": "brief_operator_planned",
                "title": "Planned operator: North Shore Recovery Club",
                "summary": "Recovery and contrast therapy operator surfaced in North Vancouver.",
                "name": "North Shore Recovery Club",
                "status": "planned",
                "source_refs": [SOURCE_REF],
            }
        ],
        "new_signals": [
            {
                "id": "brief_signal_recall",
                "title": "Health Canada recall notice",
                "summary": "Official recall signal.",
                "signal_type": "recall",
                "severity": "high",
                "trust_tier": "official",
                "source_refs": [SOURCE_REF],
            }
        ],
        "opportunity_movement": [
            {
                "id": "brief_opportunity_vancouver",
                "title": "Vancouver recovery and contrast therapy gap",
                "summary": "Recovery and contrast therapy in Vancouver is rising at 0.81.",
                "category": "recovery_contrast_therapy",
                "geo_name": "Vancouver",
                "movement": "rising",
                "delta": 0.11,
                "source_refs": [SOURCE_REF],
            }
        ],
        "new_reachable_leads": [
            {
                "id": "brief_lead_recovery",
                "title": "New reachable lead: North Shore Recovery Club",
                "summary": "Public website data is now available.",
                "name": "North Shore Recovery Club",
                "categories": ["recovery_contrast_therapy"],
                "municipality": "Vancouver",
                "contact_types": ["website"],
                "contact_count": 1,
                "source_refs": [SOURCE_REF],
            }
        ],
    }

    actions = _top_actions(sections)

    assert len(actions) == 3
    assert actions[0]["title"] == "Scout Vancouver for recovery and contrast therapy"
    assert all(action["source_refs"] for action in actions)
    assert all(action["evidence_rows"] for action in actions)
    assert actions[0]["evidence_rows"][0]["section"] == "opportunity_movement"


def test_deterministic_brief_text_is_honest_for_no_change_day() -> None:
    text = build_deterministic_brief_text(
        {
            "brief_date": "2026-06-22",
            "window_start": "2026-06-21T00:00:00Z",
            "window_end": "2026-06-22T00:00:00Z",
            "status": "no_material_changes",
            "top_actions": [],
            "counts": {
                "changed_operators": 0,
                "new_signals": 0,
                "opportunity_movement": 0,
                "new_reachable_leads": 0,
            },
            "sections": {
                "changed_operators": [],
                "new_signals": [],
                "opportunity_movement": [],
                "new_reachable_leads": [],
            },
        }
    )

    assert "No material source-backed market changes" in text
    assert "Top actions: none today" in text


def test_brief_sections_reject_unbacked_items() -> None:
    with pytest.raises(ValueError, match="missing source_refs"):
        _assert_source_backed_sections(
            {
                "changed_operators": [
                    {
                        "id": "unbacked",
                        "title": "Unbacked item",
                        "summary": "Should not persist",
                        "source_refs": [],
                    }
                ]
            }
        )


def test_window_start_covers_at_least_24_hours_after_same_day_regeneration() -> None:
    window_end = datetime(2026, 6, 22, 12, 0, tzinfo=timezone.utc)
    previous = {"generated_at": datetime(2026, 6, 22, 11, 55, tzinfo=timezone.utc)}

    start = _window_start(previous, window_end=window_end, configured_hours=1)

    assert start == datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
