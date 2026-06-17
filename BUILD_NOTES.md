# Build Notes: Phase 0 / Milestone 1

Date: 2026-06-17

## Completed

- Repo scaffold created for `apps/web`, `apps/api`, `apps/jobs`, `packages/{schemas,geo,shared}`, `db`, `infra`, and `docs`.
- `docker-compose.yml` starts PostGIS, API, jobs, and web.
- Plain SQL migrations implement the canonical schema from `AGENT_SPEC.md` section 3.2 and apply cleanly on a fresh PostGIS DB.
- `source_registry` is seeded with the MVP source rows; `rights_notes` are explicitly marked `needs_review`.
- `packages/geo/bc_gate.py` implements:
  - Metro Vancouver bbox sanity checks.
  - Optional PostGIS boundary point-in-polygon check when `metro_vancouver_boundary` exists.
  - Province/address acceptance for BC/British Columbia.
  - Text token fallback for BC, Metro Vancouver, Lower Mainland, and named municipalities.
  - Vancouver WA / Washington / Clark County / ZIP 98660-98686 negative filters.
  - StatCan Vancouver CMA `933` and BC province `59` acceptance.
- BC gate fixtures include 11 accepted BC cases and 14 rejected WA/contamination cases.
- Adapter framework and runner persist `raw_payload`, canonical `operator`, `source_event`, deterministic `signal`, `source_run`, and `rejected_record`.
- City of Vancouver business licences adapter uses the real Opendatasoft Explore API v2.1 dataset:
  - `https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/business-licences/records`
  - Recorded fixture test is checked in, so tests do not require live network.
- FastAPI endpoints implemented:
  - `GET /health`
  - `GET /operators`
  - `GET /operators/{id}`
  - `GET /signals`
  - `GET /signals/{id}`
  - `GET /admin/source-runs`
  - `GET /admin/rejected-records`
  - `GET /admin/source-registry`
- React + TypeScript + Vite UI implemented:
  - Dark map-first layout.
  - MapLibre via `react-map-gl`.
  - Clustered operator markers.
  - Reverse chronological signal feed.
  - Entity drawer with source provenance.
  - Client-side BC bbox guard before map rendering.

## How To Run

```bash
docker compose up --build
```

If the local user cannot access the Docker socket, this environment required:

```bash
sudo -n docker compose up --build
```

Then open:

- API health: `http://localhost:8000/health`
- Web: `http://localhost:5173`

The jobs service applies migrations, runs the City licence adapter once, then idles.

## Verified Commands

```bash
python3 -m pytest
python3 -m ruff check .
python3 -m mypy apps packages db
pnpm lint
pnpm typecheck
pnpm test
pnpm build
sudo -n docker compose down -v --remove-orphans
sudo -n docker compose up --build -d
curl -s http://127.0.0.1:8000/health
curl -s 'http://127.0.0.1:8000/operators?bbox=-123.3,49.0,-122.5,49.4&limit=1'
curl -s 'http://127.0.0.1:8000/signals?bbox=-123.3,49.0,-122.5,49.4&limit=1'
curl -s -o /tmp/wellness-web.html -w '%{http_code}\n' http://127.0.0.1:5173
```

Results:

- Python tests: 29 passed.
- Ruff: passed.
- Mypy: passed.
- Web unit tests: 3 passed.
- Web build: passed, with Vite chunk-size warning for MapLibre bundle.
- Fresh Compose run: PostGIS/API/jobs/web started.
- `GET /health`: `{"status":"ok"}`.
- Startup jobs run: fetched 75 real City licence records, persisted 72 canonical operators/signals, rejected 0, errors 0.
- Web returned HTTP 200.

## Stubs / Deferred Scope

- `metro_vancouver_boundary` is not seeded yet. `bc_gate` attempts PostGIS PiP when that boundary table exists and otherwise uses the required bbox + text/province/statcan fallback.
- APScheduler wiring is deferred; the jobs service runs the Phase 0 adapter once and idles.
- AI enrichment is not implemented beyond deterministic signal text, per scope.
- People graph, analytics heatmaps, paid adapters, OSM, OrgBook, RSS, WorkBC, GDELT, and regulatory feed adapters are intentionally deferred to later milestones.
- Source-rights notes are placeholders marked `needs_review`, as required for the MVP source registry seed.

## Next Milestone

Milestone 2 should add the next source adapters only after source-rights review, then extend freshness monitoring and admin UI around source runs/rejections.
