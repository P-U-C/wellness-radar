from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.app.routers import brief


class FakeResult:
    def __init__(
        self,
        row: dict[str, Any] | None = None,
        rows: list[dict[str, Any]] | None = None,
    ) -> None:
        self.row = row
        self.rows = rows or ([] if row is None else [row])

    def fetchone(self) -> dict[str, Any] | None:
        return self.row

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows


class FakeConn:
    def __init__(
        self,
        row: dict[str, Any] | None,
        rows: list[dict[str, Any]] | None = None,
    ) -> None:
        self.row = row
        self.rows = rows or ([] if row is None else [row])

    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> FakeResult:
        if "ORDER BY brief_date" in query:
            limit = int(params[0]) if params else len(self.rows)
            return FakeResult(rows=self.rows[:limit])
        if self.row is None:
            return FakeResult(None)
        if "WHERE brief_date" in query and params and params[0] != self.row["brief_date"]:
            return FakeResult(None)
        return FakeResult(self.row)


SOURCE_REF = {
    "source_name": "fixture",
    "url": "https://example.test/source",
    "trust_tier": "official",
    "seen_at": "2026-06-22T00:00:00Z",
    "source_record_id": "record-1",
    "licence": "fixture",
}


def test_latest_brief_is_public_and_returns_sections(monkeypatch) -> None:
    row = _brief_row(status="material_changes")

    @contextmanager
    def fake_connection() -> Iterator[FakeConn]:
        yield FakeConn(row)

    monkeypatch.setattr(brief, "get_connection", fake_connection)
    app = FastAPI()
    app.include_router(brief.router)
    client = TestClient(app)

    response = client.get("/brief")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "material_changes"
    assert body["top_actions"][0]["source_refs"] == [SOURCE_REF]
    assert body["sections"]["changed_operators"][0]["source_refs"] == [SOURCE_REF]


def test_no_change_brief_returns_honest_empty_sections(monkeypatch) -> None:
    row = _brief_row(status="no_material_changes", include_items=False)

    @contextmanager
    def fake_connection() -> Iterator[FakeConn]:
        yield FakeConn(row)

    monkeypatch.setattr(brief, "get_connection", fake_connection)
    app = FastAPI()
    app.include_router(brief.router)
    client = TestClient(app)

    response = client.get("/brief/2026-06-22")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "no_material_changes"
    assert body["top_actions"] == []
    assert body["sections"]["changed_operators"] == []
    assert "No material" in body["brief_text"]


def test_recent_briefs_lists_history(monkeypatch) -> None:
    latest = _brief_row(status="material_changes")
    prior = _brief_row(status="no_material_changes", include_items=False)
    prior["id"] = "daily_brief_2026_06_21"
    prior["brief_date"] = date(2026, 6, 21)
    rows = [latest, prior]

    @contextmanager
    def fake_connection() -> Iterator[FakeConn]:
        yield FakeConn(latest, rows=rows)

    monkeypatch.setattr(brief, "get_connection", fake_connection)
    app = FastAPI()
    app.include_router(brief.router)
    client = TestClient(app)

    response = client.get("/brief/recent?limit=2")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["count"] == 2
    assert [item["brief_date"] for item in body["items"]] == ["2026-06-22", "2026-06-21"]


def _brief_row(*, status: str, include_items: bool = True) -> dict[str, Any]:
    now = datetime(2026, 6, 22, 12, 0, tzinfo=timezone.utc)
    sections: dict[str, list[dict[str, Any]]] = {
        "changed_operators": [],
        "new_signals": [],
        "opportunity_movement": [],
        "new_reachable_leads": [],
    }
    top_actions: list[dict[str, Any]] = []
    if include_items:
        sections["changed_operators"] = [
            {
                "id": "brief_operator_1",
                "title": "Planned operator: Test",
                "summary": "Test summary.",
                "source_refs": [SOURCE_REF],
                "confidence_score": 0.9,
            }
        ]
        top_actions = [
            {
                "id": "brief_action_1",
                "title": "Track planned opening: Test",
                "summary": "Test summary.",
                "action_type": "operator",
                "evidence_rows": [
                    {
                        "section": "changed_operators",
                        "item_id": "brief_operator_1",
                        "title": "Planned operator: Test",
                        "source_refs": [SOURCE_REF],
                    }
                ],
                "source_refs": [SOURCE_REF],
            }
        ]
    return {
        "id": "daily_brief_2026_06_22",
        "brief_date": date(2026, 6, 22),
        "generated_at": now,
        "window_start": now,
        "window_end": now,
        "status": status,
        "brief_text": "No material source-backed market changes were detected.",
        "sections": sections,
        "top_actions": top_actions,
        "counts": {
            "changed_operators": len(sections["changed_operators"]),
            "new_signals": 0,
            "opportunity_movement": 0,
            "new_reachable_leads": 0,
            "top_actions": len(top_actions),
        },
        "source_refs": [SOURCE_REF] if include_items else [],
        "narrative_model": "deterministic-template-v1",
    }
