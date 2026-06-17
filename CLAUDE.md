# CLAUDE.md — Agent Instructions for P-U-C/wellness-radar

You are working in the `P-U-C/wellness-radar` repository.

## Product

Vancouver Wellness Radar is a map-first Metro Vancouver wellness market-intelligence console. It is not a clinical health product.

The product surfaces:
- operator/facility map
- live signal feed
- people/org directory and graph
- white-space/opportunity analytics

Lead wedge:
- recovery
- contrast therapy
- sauna
- cold plunge
- social wellness

## Non-Negotiables

1. No patient-level data.
2. No clinical decision support.
3. No medical advice.
4. No private health attributes.
5. No private mobility traces.
6. No LinkedIn scraping.
7. No raw social firehose in MVP.
8. No geo-aware record persists without `bc_gate`.
9. No displayed record without `source_refs`.
10. No adapter ships without `source_registry.rights_notes`.
11. No placeholders count as done unless ticket explicitly says seed/stub.
12. Do not push directly to `main`.

## Architecture

- Frontend: React + TypeScript + Vite
- Map: MapLibre GL JS
- API: FastAPI
- Jobs: Python adapters
- Store: PostgreSQL + PostGIS
- People graph: Sigma.js + graphology
- AI: enrichment only, never source of truth

## Required Flow

Source -> raw_payload -> normalize -> bc_gate -> canonical table -> source_event -> signal -> API -> UI

## BC Geo Gate

Every geo-aware adapter must call:

```python
bc_gate(record)
```

Reject:
- Vancouver, WA
- Washington
- Clark County
- ZIP 98660-98686

Accept only:
- Metro Vancouver / BC coordinates
- Province BC / British Columbia
- StatCan Vancouver CMA 933 / BC 59 where relevant

## Testing Expectations

Before marking a task complete:
- run unit tests
- run geo-filter tests
- run adapter fixture tests if adapter touched
- run type checks
- run lint
- ensure migrations apply from clean DB

## Source Adapter Definition of Done

An adapter is done only when:
- rights row exists
- fetches real records
- stores raw payloads
- normalizes canonical records
- runs bc_gate if geo-aware
- logs rejections
- upserts idempotently
- writes source_event
- populates source_refs
- has fixture tests

## AI Rules

AI may generate:
- summary
- why_it_matters
- category suggestions
- severity suggestions
- entity match candidates

AI may not:
- invent facts
- create unbacked signals
- infer private personal/health information
- overwrite deterministic facts without review

## PR Rules

Each PR must include:
- summary
- tests run
- screenshots for UI
- migration notes if DB changed
- source-rights note if adapter changed
- risks/rollback section

Do not weaken these instructions.
