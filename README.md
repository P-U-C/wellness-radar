# Vancouver Wellness Radar

Map-first **market-intelligence console** for the public Metro Vancouver wellness economy — operators, signals, people, and opportunity, all built from source-backed public data with provenance on every record.

The lead wedge is **recovery / contrast therapy** (sauna, cold plunge, contrast, regeneration), but the platform tracks the full wellness category space: fitness & movement, spa & bodywork, mental wellness, nutrition, and clinical-adjacent services. It is **not** a clinical health product.

> **Status:** end-to-end build complete across milestones **M0–M4**. 47 automated tests passing. Runs locally with **zero external keys or secrets** (built-in map style, deterministic AI fallback). Several data sources and the production launch path still require human source-rights review and deployment ownership — see [Honest Status](#honest-status).

---

## What it does

```text
public sources ──▶ adapters ──▶ bc_gate ──▶ PostGIS ──▶ FastAPI read/admin API ──▶ React + MapLibre console
 (City licences, OSM,    (normalize +   (BC-only      (operators,     (public reads +        (map · signal feed ·
  OrgBook, RSS, Gov      provenance)    geo-filter)    signals,        RBAC admin)             people graph ·
  feeds, StatCan,                                      people,                                 opportunity analytics ·
  manual seeds)                                        analytics)                              kiosk mode)
```

Four surfaces on one corpus:

- **Operator map** — clustered MapLibre map of Metro Vancouver wellness operators; click a pin to filter/highlight the feed and open a provenance drawer. The map never renders a record outside the BC bounding box.
- **Signal feed** — reverse-chronological feed of source-backed events (new operators, news, regulatory recalls, OSM observations) with a generated `why_it_matters`. Click a card to fly the map to it.
- **People graph** — Sigma.js / graphology force-directed graph of public professional relationships (people, orgs, operators, events) with Louvain communities, centrality sizing, and explainable influence scores. **Public professional data only** — no patient, clinical, social, or LinkedIn data.
- **Opportunity analytics** — white-space heatmap, opportunity scorecards with full component breakdowns, category velocity (30/90/180-day), and peer-city trend tiles. Scores are explicitly framed as supply-demand signals, not guaranteed economic attractiveness.

Plus a fullscreen **kiosk / TV mode** (`/?mode=kiosk`) with an ambient live-feed overlay.

---

## Architecture

| Layer | Stack |
|-------|-------|
| Web | React + TypeScript + Vite, MapLibre GL (`react-map-gl`), Sigma.js + graphology |
| API | FastAPI (Python 3.10), token-backed RBAC, Prometheus-style `/metrics` |
| Jobs | Python adapter framework + runner (one-shot startup sequence; APScheduler placeholder) |
| Data | PostgreSQL + PostGIS |
| AI | Provider interface — deterministic local enricher by default; Claude provider behind `ANTHROPIC_API_KEY`. AI is enrichment only, never a source of truth |
| Infra | Docker Compose (db · api · jobs · web); GitHub Actions CI |

### Repository layout

```
apps/
  api/         FastAPI app — read endpoints, admin/RBAC, observability, exports
  jobs/        adapter runner + milestone job sequences (m2, m3)
  web/         React + MapLibre + Sigma console (and kiosk mode)
packages/
  schemas/     canonical record schemas
  geo/         bc_gate — the BC-only geo guard
  shared/      shared utilities
db/            SQL migrations (001–005) + seed CSVs
docs/          ADRs, analytics methodology, data-sources, governance, runbooks, people
infra/         docker images, GitHub Actions workflow, terraform placeholder
AGENT_SPEC.md  the full build specification
CLAUDE.md      the binding build manifest (non-negotiable constraints)
```

### Two invariants enforced everywhere

1. **`bc_gate`** — every geo-aware record must pass a Metro Vancouver / BC filter before it persists (bbox + PostGIS point-in-polygon where a boundary exists, province/address tokens, StatCan CMA 933 / province 59, and negative Washington-State filters incl. ZIP 98660–98686). This stops Vancouver WA contamination at the boundary, and every rejection is written to `rejected_record`.
2. **Provenance** — no displayed record exists without `source_refs`, and no adapter runs without a row in the source-rights registry. The UI surfaces provenance and freshness age on operators, signals, people scores, map pins, and opportunity scorecards.

---

## Data sources

Ingested via the adapter framework (each TESTED against a recorded fixture — no network required in CI):

- **City of Vancouver** business licences (Opendatasoft Explore API)
- **OpenStreetMap** Overpass — wellness POIs (sauna, spa, fitness, massage, …)
- **OrgBook BC** — registered-entity enrichment / legal-name matching
- **Local RSS** — Daily Hive, Vancouver Sun, BIV, STIR, Scout (wellness-relevant, BC text-gated)
- **Official feeds** — BC Gov News (Health) RSS, Health Canada product recalls
- **Statistics Canada** WDS — CMA/CSD population & business-count denominators
- **Manual seeds** — 12 named Metro Vancouver recovery/contrast operators and a small public-professional people set, both with explicit source refs and geocoding confidence

The complete rights matrix is in [`docs/governance/source_rights_matrix.md`](docs/governance/source_rights_matrix.md). Sources still pending human legal review are honestly marked `needs_review` and must clear that review before public production use.

---

## Run it

```bash
docker compose up --build      # db · api · jobs · web; jobs ingests + runs the m2/m3 sequences on startup
```

| | |
|---|---|
| Web dashboard | http://localhost:5173 |
| Kiosk mode | http://localhost:5173?mode=kiosk |
| API health | http://localhost:8000/health |
| Metrics | http://localhost:8000/metrics |
| PostGIS | localhost:5432 |

Local Compose uses non-secret placeholder RBAC tokens (`local-analyst-token`, `local-admin-token`). Public read endpoints are open; `/admin/*` reads need analyst, admin writes need admin. Do not reuse local tokens outside local development.

### Selected API surface

Public reads: `/operators`, `/operators/{id}`, `/signals`, `/signals/{id}`, `/people`, `/people/{id}`, `/people-graph`, `/trends`, `/analytics/whitespace`, `/analytics/opportunity-scorecards`, `/analytics/category-velocity`, `/analytics/methodology`, `/source-registry`.

Admin (RBAC): `/admin/observability`, `/admin/source-freshness`, `/admin/source-runs`, `/admin/rejected-records`, `/admin/audit-logs`, `/admin/alert-subscriptions`, `/admin/alerts/evaluate`, `/admin/alerts/dispatch-stub`, `/admin/exports/{dataset}` (CSV/JSON), `/admin/snapshots`, `/admin/me`. People-scoring corrections: `POST /people/{id}/correction-requests`.

---

## Quality gates

```bash
python3 -m pytest          # Python: 44 passing
python3 -m ruff check .
python3 -m mypy apps packages db
pnpm lint && pnpm typecheck && pnpm test    # web: 3 passing
pnpm build
```

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs web lint/typecheck/test, Python lint/typecheck/test, the geo and adapter-fixture tests, the full suite, and a clean-DB migration check. Migrations `001`–`005` apply cleanly on a fresh PostGIS database.

---

## Governance

- **People** — public professional data only. No patient data, clinical content, medical advice, raw social, or LinkedIn scraping. Influence scores are explainable ("why this person appears") and reversible, and a correction-request workflow with audit logging is built in (a human owner + response SLA must be assigned before public launch).
- **Attribution** — every record carries its source; raw payloads are retained per source-licence policy.
- **Audit** — adapter runs, rejections, upserts, AI enrichment, admin writes, dispatches, snapshots, and correction requests are written to `audit_log`.

The binding constraints are in [`CLAUDE.md`](CLAUDE.md) and are not to be weakened.

---

## Honest status

Built and verified across M0–M4; the following are intentionally stubbed or pending human/production ownership and are **not** to be presented as live:

- **Alert delivery** is a stub — `/admin/alerts/dispatch-stub` writes `alert_dispatch` rows; external email/webhook/PagerDuty delivery is not configured.
- **Peer-city trends** are fixture-backed and labelled as such in the API and UI — they are not live Google Trends.
- **Source rights** — `manual_seed`, `manual_people_csv`, `osm_overpass`, `orgbook_bc`, `local_rss`, and `peer_city_trends_fixture` still need human legal review before public production.
- **CRE adapter** was deliberately not added (its backlog row is `needs-human-review`).
- **Scheduler** — the jobs service runs the ingestion sequence once on startup then idles; production needs real scheduled jobs or an external orchestrator.
- **Production launch** needs real deployment secrets, external alert sinks, monitoring sinks, and a people-correction owner configured outside the repository.

Full milestone-by-milestone build log, verified command output, and the production gate are in [`BUILD_NOTES.md`](BUILD_NOTES.md). The complete specification is [`AGENT_SPEC.md`](AGENT_SPEC.md); binding constraints are in [`CLAUDE.md`](CLAUDE.md).
