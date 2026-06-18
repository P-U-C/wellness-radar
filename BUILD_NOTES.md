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

## M2

Date: 2026-06-18 UTC

### Completed Against Exit Checklist

- OSM Overpass adapter added for Metro Vancouver wellness POIs (`leisure=sauna`, `leisure=fitness_centre`, `amenity=spa`, `shop=massage`, and selected healthcare/massage tags). It uses explicit Overpass request headers, source refs, BC gate, raw payload storage, source events/signals, and exact-name dedupe against existing operators.
- OrgBook BC enrichment added. Existing operators are searched through the OrgBook API, matched conservatively against legal names, linked to `organization` rows, and marked `matched`/`unmatched` explicitly with `orgbook_match_status`, `orgbook_match_confidence`, and `orgbook_id` when available.
- Local RSS adapter added for BC-local outlets: Daily Hive, Vancouver Sun, BIV, STIR Vancouver, and Scout. It parses RSS/Atom without live-network tests, filters for wellness relevance, applies BC text gate, and writes source events/signals.
- Official feed adapters added for BC Gov News Health RSS and Health Canada health-products recalls. BC Gov Health is BC text gated; Health Canada recalls are official national regulatory signals without geo.
- Manual recovery-club seed adapter added with 12 named Metro Vancouver recovery/contrast/spa operators in `db/seeds/manual_recovery_operators.csv`, all with source refs and explicit geocoding confidence.
- Manual people CSV import added in `db/seeds/manual_people.csv` and importer code. It imports public professional records only, with source refs and no LinkedIn/social/private/patient data.
- People leaderboard stub added to the web app with sortable confidence/name/role views.
- AI signal enrichment service added with a provider interface:
  - default: deterministic local provider, no network/key required;
  - optional: Claude provider behind `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL`.
  It only fills generated summary/why/category suggestions/severity suggestion metadata and stores prompt version, model, generated fields, and AI confidence without overwriting deterministic facts.
- Source freshness admin endpoint and UI panel added. It shows latest source-run status, SLA-derived stale flags, and rejected-record counts.
- Frontend signal feed and map sync updated:
  - click feed card with an operator flies to map and opens the drawer;
  - click map pin selects the operator and filters/highlights the feed;
  - non-geocoded official/news signals still render in the feed.

### How To Run / Verify

```bash
sudo -n docker compose up --build -d
curl -s http://127.0.0.1:8000/health
curl -s 'http://127.0.0.1:8000/operators?bbox=-123.3,49.0,-122.5,49.4&limit=3'
curl -s 'http://127.0.0.1:8000/signals?bbox=-123.3,49.0,-122.5,49.4&limit=5'
curl -s 'http://127.0.0.1:8000/people?limit=3'
curl -s 'http://127.0.0.1:8000/admin/source-freshness'
```

Open the web app at `http://localhost:5173`.

### Verified Commands

```bash
python3 -m pytest
python3 -m ruff check .
python3 -m mypy apps packages db
pnpm lint
pnpm typecheck
pnpm test
pnpm build
sudo -n docker compose down -v --remove-orphans
sudo -n docker compose up -d db
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar python3 -m db.migrate
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar python3 -m apps.jobs.runner m2 --limit 20
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar python3 -m apps.jobs.runner osm_overpass --limit 20
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar python3 -m apps.jobs.runner ai_enrichment --limit 100
sudo -n docker compose up --build -d
```

Results:

- Python tests: 35 passed.
- Ruff: passed.
- Mypy: passed.
- Web lint/typecheck: passed.
- Web unit tests: 3 passed.
- Web build: passed with the existing MapLibre/Vite chunk-size warning.
- Clean DB migrations applied: `001`, `002`, `003`.
- Clean M2 run (`--limit 20`) succeeded for City, manual seed, RSS, BC Gov, Health Canada, OrgBook, people import, and AI enrichment. OSM initially returned Overpass HTTP 406 due default httpx headers; fixed with explicit user-agent/accept headers and reran successfully: 20 fetched, 19 persisted, 0 rejected.
- Full Compose M2 startup run completed:
  - City licences: 75 fetched, 72 persisted.
  - Manual seed: 12 fetched, 12 persisted.
  - OSM Overpass: 75 fetched, 68 persisted.
  - Local RSS: 75 fetched, 4 persisted.
  - BC Gov Health RSS: 10 fetched, 10 persisted.
  - Health Canada recalls: 3 fetched, 3 persisted.
  - OrgBook BC: 75 fetched, 75 persisted.
  - Manual people CSV: 6 fetched, 6 persisted.
  - AI enrichment: 75 enriched during Compose run; 140 total enriched signals after verification reruns.
- Source freshness endpoint reported 0 stale enabled sources after jobs completed.
- Coverage checks on the clean DB:
  - operators without source refs: 0;
  - signals without source refs: 0;
  - people without source refs: 0;
  - manual recovery operators: 12;
  - OrgBook matched organizations: 53;
  - OrgBook unmatched organizations: 28.
- API health returned `{"status":"ok"}` and web root returned HTTP 200.

### Stubbed / Deferred

- People leaderboard is intentionally a stub for M2: sortable public-professional records only, no influence scoring or graph centrality.
- AI uses deterministic local enrichment unless `ANTHROPIC_API_KEY` is set. The Claude provider is wired but not exercised in this environment because no key is assumed or required.
- Local RSS per-feed failures are isolated and do not fail the whole adapter. Feed limits can mean one outlet supplies all fetched records in a small run; M3 should add per-outlet run metrics if outlet coverage becomes a product requirement.
- APScheduler remains deferred; jobs run the M2 sequence once, then idle.

### M3 Pickup

- Real entity-resolution workflow beyond exact-name dedupe.
- Opportunity heatmap, category velocity, peer-city trends, Sigma.js graph, and influence score explainability.
- Source-rights/legal review for production attribution and republication policy.
- Per-source/outlet scheduling, retries, and alerting instead of one-shot startup jobs.

## M3

Date: 2026-06-18 UTC

### Completed Against Exit Checklist

- Entity resolution added with `entity_resolution_match` and `entity_alias`. Matches use deterministic rules over normalized names, OrgBook/registry IDs, municipality, and `pg_trgm` similarity. Merges are logical aliases only, with confidence, provenance, review status, and reversible state.
- Category enum is frozen in `category_taxonomy` and enforced on `operator.categories`. Draft NAICS mappings are seeded in `naics_category_crosswalk` and documented in `docs/analytics/category_naics_crosswalk.md` as `needs-human-review`.
- StatCan denominator adapter added as `statcan_wds`. It stores CMA/CSD geography and population/business-count denominators from a recorded fixture, records raw payloads/source runs, writes source refs, and runs `bc_gate` before geography persist.
- White-space heatmap and opportunity scorecards added with full component breakdown, source refs, source confidence, trace payloads, and a caveat that scores are supply-demand signals, not guaranteed economic attractiveness.
- Category velocity analytics added for 30/90/180 day windows: new operators, jobs, events, and news/signal velocity.
- Peer-city trend provider interface added with deterministic fixture fallback for Vancouver, Toronto, Seattle, Austin, and Melbourne wedge terms. API/UI clearly mark these rows as stub-backed.
- Influence scoring added with the s.11.3 components, locality multiplier, recency decay, source confidence, persisted breakdowns, and “why this person appears” explanations. Public professional seed data remains the only people input.
- Sigma.js people graph added with graphology, ForceAtlas2 worker layout, Louvain communities, and centrality sizing. Graph nodes cover people, orgs, operators, and events; edges include employee/speaker/mentioned-with style public relationships.
- M3 API endpoints added: `/analytics/whitespace`, `/analytics/opportunity-scorecards`, `/analytics/category-velocity`, `/analytics/methodology`, `/trends`, and `/people-graph`.
- Web dashboard now renders opportunity scorecards, velocity, peer-city trend tiles, influence breakdowns, Sigma graph, and a white-space map overlay.
- Compose jobs now run `m2` then `m3` on startup.

### How To Run / Verify

```bash
sudo -n docker compose up --build -d
curl -s http://127.0.0.1:8000/health
curl -s 'http://127.0.0.1:8000/analytics/whitespace?category=recovery_contrast_therapy&limit=1'
curl -s 'http://127.0.0.1:8000/analytics/opportunity-scorecards?category=recovery_contrast_therapy&limit=1'
curl -s 'http://127.0.0.1:8000/analytics/category-velocity?category=recovery_contrast_therapy'
curl -s 'http://127.0.0.1:8000/trends?term=cold%20plunge'
curl -s 'http://127.0.0.1:8000/people?sort=influence&limit=1'
curl -s 'http://127.0.0.1:8000/people-graph'
```

Open the web app at `http://localhost:5173`.

### Verified Commands

```bash
python3 -m pytest
python3 -m ruff check .
python3 -m mypy apps packages db
pnpm lint
pnpm typecheck
pnpm test
pnpm build
sudo -n docker compose down -v --remove-orphans
sudo -n docker compose up -d db
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar python3 -m db.migrate
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar python3 -m apps.jobs.runner m2 --limit 20
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar python3 -m apps.jobs.runner m3
sudo -n docker compose up --build -d
```

Results:

- Python tests: 40 passed.
- Ruff: passed.
- Mypy: passed.
- Web lint/typecheck: passed.
- Web unit tests: 3 passed.
- Web build: passed with the existing Vite large chunk warning, now larger because Sigma/graphology are bundled.
- Clean DB migrations applied: `001`, `002`, `003`, `004`.
- Clean M2 run with `--limit 20` succeeded across City, manual seed, OSM, RSS, official feeds, OrgBook, people import, and AI enrichment.
- Clean M3 run succeeded:
  - Entity resolution: 0 fetched/persisted on the clean sample because existing exact-name/OrgBook dedupe left no unresolved duplicate pairs.
  - StatCan denominators: 6 fetched, 30 persisted, 0 rejected.
  - Opportunity analytics: 20 fetched, 32 persisted.
  - Peer-city trends: 30 fetched, 30 persisted.
  - People graph: 76 fetched, 97 persisted in the clean sample run; full Compose run produced 227 nodes and 78 edges after the larger M2 startup.
  - Influence scoring: 6 fetched, 6 persisted.
- Full Compose startup returned API health `{"status":"ok"}` and web root HTTP 200.
- Endpoint smoke checks confirmed opportunity rows include component breakdown/source confidence/source refs; trends return `is_stub: true`; people return influence components and explanation.

### Stubbed / Needs Review

- Peer-city trend tiles are intentionally stub-backed by `peer_city_trends_fixture` because no reviewed Google Trends API/key is available. They must not be presented as live Google Trends data.
- StatCan denominator data uses a recorded M3 fixture shaped for the WDS/Census Profile flow. Production table/vector selection, attribution text, and caching policy remain `needs_review`.
- NAICS crosswalk is drafted and flagged `needs-human-review`; no sign-off is claimed.
- The `transit_access` score component is a centroid-to-core accessibility proxy for M3, not a true transit model.
- Entity resolution has working deterministic merge/candidate logic, but the clean verification dataset produced no new unresolved matches.

### M4 Pickup

- Replace trend fixture fallback with a reviewed live provider or keep a clearly labelled non-live mode.
- Replace CSD centroid proxy with reviewed neighborhood polygons and transit-access data.
- Add correction/request-update workflow for people records before public launch.
- Add RBAC/audit/export/subscription production hardening from Milestone 4.
- Add CRE inputs only after source-rights review.
