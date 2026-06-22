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

## COVERAGE

Date: 2026-06-22 UTC

### Coverage Proof

- Pre-coverage operator count in the app DB: 148.
- After broadened OSM plus municipal facilities: 1,814 operators.
- Broadened OSM run: fetched 2,000, persisted 529, rejected 0, errors 0.
- Municipal facilities run: fetched 1,260, persisted 1,256, rejected 3, errors 0. Rejections were `coordinates outside Metro Vancouver bbox`.
- Bundle synthesis after coverage: fetched 2,871 inputs, persisted 2,747 bundle/member/person rows.

### New Category Counts

- `public_recreation`: 1,297
- `field_track_sports`: 683
- `racquet_court_sports`: 264
- `ice_sports`: 97
- `aquatics`: 72
- `climbing`: 70
- `combat_sports`: 40

### Type Evidence

- Pickleball-backed operators: 32
- Tennis-backed operators: 114
- Climbing-backed operators: 69
- Boxing/martial arts-backed operators: 39
- Yoga/pilates-backed operators: 66
- Swimming/pool-backed operators: 76
- Ice rink/skating/hockey-backed operators: 103

### Municipal Coverage

- Vancouver: 810 operators
- Surrey: 413 operators
- West Vancouver: 83 operators
- Burnaby: 53 operators

West Vancouver examples now present: Aspen Park, Batchelor Bay Park, Butterfly Park, Caulfeild Green, Caulfeild Park, Clovelly Walk, Cypress Falls Park, Cypress Trails Park.

### Bundle Coverage

- Public recreation courts & fields: 1,423 members
- Pickleball & court sports: 264 members
- Aquatics & ice rinks: 166 members
- Yoga & pilates: 71 members
- Climbing & bouldering: 70 members
- Combat & martial arts: 41 members

Completeness checks after ingest: 0 operators missing `source_refs`, 0 source events missing `source_refs`, and 0 signals missing `source_refs`. Source registry rows with `rights_notes` exist for `municipal_facilities`, West Vancouver, Vancouver, Surrey, Burnaby, Richmond (`needs_review`), North Vancouver (`needs_review`), and OSM. Richmond and North Vancouver are registered but skipped until clean fetch endpoints are adopted.

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

## M4

Date: 2026-06-18 UTC

### Completed Against Exit Checklist

- RBAC added for API protected surfaces:
  - `viewer`, `analyst`, and `admin` roles are token-backed.
  - Public read endpoints remain open.
  - `/admin/*` read endpoints require analyst/admin permission.
  - admin-only writes such as snapshot creation and alert dispatch stubs require admin permission.
  - Tests cover missing token, insufficient role, analyst read, analyst write denial, and admin write allow.
- Audit logging added:
  - `audit_log` stores structured admin/system events with request ID, source name, source run ID, entity/source-event/signal IDs, reject reason, prompt version, actor role, and metadata.
  - Adapter starts/completions, record rejections, source-event/signal upserts, AI enrichment, alert subscription writes, dispatch stubs, snapshots, and people correction requests are audited.
- Alert subscriptions added:
  - `alert_subscription` stores owner email, categories, geography JSON, enabled alert conditions, channel, and target.
  - `/admin/alerts/evaluate` evaluates all s.15.3 alert conditions.
  - `/admin/alerts/dispatch-stub` writes stub dispatch rows to `alert_dispatch`.
- Export and snapshots added:
  - `/admin/exports/{operators|signals|graph}?format={json|csv}` exports source-backed records with provenance/freshness.
  - `/admin/snapshots` creates/list export snapshots in `export_snapshot`.
- Kiosk / TV mode added:
  - `/?mode=kiosk` renders a fullscreen map with ambient live feed overlay.
  - Main dashboard links to kiosk mode.
- Observability added:
  - Structured JSON API request logs include request ID, method/path, status, latency, and role when available.
  - `/metrics` exposes Prometheus-style aggregate metrics.
  - `/admin/observability` exposes API latency/error, map query latency, adapter success/failure, records fetched/persisted/rejected, source freshness age, AI cost/error counters, WA contamination rejects, geocoding hit rate, fuzzy-match confidence buckets, and alert status.
- Governance/UI hardening added:
  - Operators, signals, people scoring, map pin inspection, entity drawer, and opportunity scorecards expose provenance and freshness age.
  - People scoring correction workflow added with `people_correction_request`, `POST /people/{person_id}/correction-requests`, audit logging, and governance docs.
  - Source-rights matrix documented in `docs/governance/source_rights_matrix.md`; official open-government sources were resolved where current official licences were clear, while unresolved sources remain honestly marked `needs_review`.
- Deployment and workflow hardening added:
  - Runbooks added for local, dev, staging, production, and incidents.
  - `.env.example` contains placeholder-only secret/config names.
  - CI explicitly runs web checks, Python lint/typecheck, geo tests, adapter fixture tests, full pytest, and migration check.
  - `infra/github/workflows/ci.yml` mirrors the active `.github/workflows/ci.yml`.
  - CODEOWNERS covers protected paths including workflow files.
  - PR template added per `CLAUDE.md`.
- M3 idempotency hardening:
  - Entity-resolution candidates are deduped by active duplicate before insert, fixing a duplicate-key issue found during M4 Compose verification.

### How To Run / Verify

```bash
sudo -n docker compose up --build -d
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/metrics
curl -s -H 'Authorization: Bearer local-analyst-token' http://127.0.0.1:8000/admin/me
curl -s -H 'Authorization: Bearer local-analyst-token' http://127.0.0.1:8000/admin/observability
curl -s -H 'Authorization: Bearer local-analyst-token' http://127.0.0.1:8000/admin/alerts/evaluate
curl -s -H 'Authorization: Bearer local-analyst-token' 'http://127.0.0.1:8000/admin/exports/operators?format=csv'
curl -s -H 'Authorization: Bearer local-admin-token' \
  -H 'Content-Type: application/json' \
  -d '{"snapshot_type":"operators","format":"json"}' \
  http://127.0.0.1:8000/admin/snapshots
```

Open:

- Web dashboard: `http://localhost:5173`
- Kiosk mode: `http://localhost:5173?mode=kiosk`

### Verified Commands

```bash
python3 -m pytest -q
python3 -m ruff check .
python3 -m mypy apps packages db
pnpm lint
pnpm typecheck
pnpm test
pnpm build
sudo -n docker compose down -v --remove-orphans
sudo -n docker compose up -d db
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar python3 -m db.migrate
sudo -n docker compose up --build -d
```

Results:

- Python tests: 44 passed.
- Web unit tests: 3 passed.
- Total tests: 47 passed.
- Ruff: passed.
- Mypy: passed.
- Web lint/typecheck/build: passed; Vite still reports the existing large chunk warning from map/graph dependencies.
- Clean PostGIS migrations applied: `001`, `002`, `003`, `004`, `005`.
- Compose rebuilt and started API/jobs/web/db.
- API health returned `{"status":"ok"}`.
- Web dashboard and kiosk route returned HTTP 200.
- RBAC smoke:
  - unauthenticated `GET /admin/me`: HTTP 401;
  - analyst token `GET /admin/me`: HTTP 200;
  - analyst token `POST /admin/snapshots`: HTTP 403;
  - admin token `POST /admin/snapshots`: created a ready snapshot.
- Compose startup job results after rebuild:
  - City licences: 75 fetched, 72 persisted.
  - Manual seed: 12 fetched, 12 persisted.
  - OSM Overpass: 75 fetched, 68 persisted.
  - Local RSS: 75 fetched, 5 persisted.
  - BC Gov Health RSS: 10 fetched, 10 persisted.
  - Health Canada recalls: 3 fetched, 3 persisted.
  - OrgBook BC: 75 fetched, 75 persisted.
  - Manual people CSV: 6 fetched, 6 persisted.
  - AI enrichment: 75 enriched per startup run.
  - Entity resolution: 0 fetched/persisted on the final rebuilt run because active matches already existed; no errors.
  - StatCan denominators: 6 fetched, 30 persisted.
  - Opportunity analytics: 20 fetched, 32 persisted.
  - Peer-city trends: 30 fetched, 30 persisted.
  - People graph: 226 fetched, 303 persisted.
  - Influence scoring: 6 fetched, 6 persisted.
- `/admin/observability` reported 0 API errors, all latest enabled source freshness ages within SLA, 0 WA contamination rejects, geocoding hit rate `0.9122`, and fuzzy-match bucket count with high-confidence matches present.

### Stubbed / Needs Review

- Alert dispatch is intentionally a stub that writes `alert_dispatch` rows; external email/webhook/PagerDuty delivery is not configured.
- `peer_city_trends_fixture` remains stub-backed and must not be presented as live Google Trends.
- CRE adapter spike remains unimplemented because the backlog row is `needs-human-review`; no unreviewed CRE source was added.
- Enabled sources still requiring human source-rights review before public launch: `manual_seed`, `manual_people_csv`, `osm_overpass`, `orgbook_bc`, `local_rss`, and `peer_city_trends_fixture`.
- Disabled backlog sources still requiring review before enablement: `clinicaltrials_gov`, `gdelt_doc`, `healthlink_bc_locator`, `vch_fraser_health_pages`, and `workbc_job_bank`.
- Production deployment secrets, real external alert delivery, and public people-correction ownership/SLA must be configured outside the repository before public launch.
- APScheduler remains an idle placeholder from earlier milestones; the Compose jobs service still runs startup sequences and idles.

## CM1 — Contacts

### What Landed

- Added source-backed public contact capture for operators: `phone`, `website`, `social_links`, and an `operator_contact` method table with per-contact `source_ref` and confidence.
- OSM Overpass now extracts public `phone`/`contact:phone`, `website`/`contact:website`, `email`/`contact:email`, `contact:instagram`, and `contact:facebook` tags.
- City of Vancouver business licences now surface public business phone/website fields when present and carry public licence/business-name candidates into the people layer when they look like named public operators.
- Manual recovery seeds now preserve their public operator websites as contacts.
- `/operators`, `/operators/{id}`, and new `/leads` return contact arrays with provenance; `/admin/exports/leads` and `/admin/exports/people` support CSV/JSON.
- Operator detail, map drawer, search, and opportunity panel now show reachable-contact counts and public contact links.

### Verified Coverage

Fixture-backed clean DB run, after migrations `001`-`007`, m2 fixture ingest, and m3 analytics:

- Source-backed operators: 15.
- Operators with at least one public contact: 13 of 15 (`86.67%`).
- Contact rows: 19 total: 13 website, 3 phone, 1 email, 2 social.
- `/operators` metadata reported the same contact coverage: 13 of 15.
- `/operators/{id}` sample: `Art of Sauna` returned 4 contacts; first contact source was OSM node `10555619247`.
- `/leads?limit=20` returned 13 reachable operators.
- `/admin/exports/leads?format=csv` produced 19 contact rows with contact/provenance columns.
- `/admin/exports/people?format=json` returned 7 people, including the fixture-backed City licence public-name candidate.

### Fixture Ingest Evidence

- Manual seed: 12 fetched, 12 persisted, 0 rejected.
- City Vancouver business licence fixture: 3 fetched, 3 persisted, 0 rejected.
- OSM Overpass fixture: 3 fetched, 2 persisted, 1 rejected by `bc_gate` for Vancouver WA.
- Manual people CSV: 6 fetched, 6 persisted.
- M3 analytics on the same clean DB completed with 0 errors.

### Limitation

Contact coverage is mostly websites. Phones, emails, and social handles are sparse in the reviewed public fixtures; this is expected and must not be filled by inference. No LinkedIn data, private personal data, patient data, or health attributes were added.

### CM1 Commands Run

```bash
python3 -m pytest apps/jobs/tests/test_m2_adapters.py apps/jobs/tests/test_city_vancouver_licences.py packages/geo/tests/test_bc_gate.py
python3 -m pytest
python3 -m ruff check apps packages db
python3 -m mypy apps packages db
pnpm lint
pnpm typecheck
pnpm test
pnpm build
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar_cm1_clean python3 -m db.migrate
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar_cm1_clean python3 -m apps.jobs.runner m3
```

Results:

- Python tests: 50 passed.
- Web tests: 9 passed.
- Ruff: passed.
- Mypy: passed.
- Web lint/typecheck/build: passed; Vite still reports the existing large chunk warning from map/graph dependencies.
- Clean PostGIS migrations applied from empty DB: `001`, `002`, `003`, `004`, `005`, `006`, `007`.

## CM2 — Daily Brief

### What Landed

- Added `daily_brief` persistence and `opportunity_score_snapshot` history in migration `008_daily_brief.sql`.
- Added deterministic daily brief generation in `apps/jobs/analytics/daily_brief.py`.
- Brief sections cover:
  - changed/newly planned operators;
  - new high-severity or official/reputable signals;
  - opportunity score movement versus the previous score snapshot;
  - newly reachable public leads from `operator_contact`.
- Each section item and each action carries `source_refs`; generation raises if a displayed item/action is unbacked.
- Top actions are ranked deterministically from evidence rows and cite those evidence rows.
- AI narrative enrichment is optional and only used when `ANTHROPIC_API_KEY` is present; deterministic template text is the default and facts/items remain source-backed.
- Added public reader routes:
  - `GET /api/brief`
  - `GET /api/brief/{date}`
- Added scheduler delivery on the existing alert rail with separate condition `daily_market_brief`; ops-health alerts remain separate.
- Added a console Today / Market Brief panel showing top actions, sections, and source links.

### Fixture Loop Evidence

Clean DB migration:

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar_cm2_loop python3 -m db.migrate
```

Applied cleanly from empty DB through `001`-`008`.

Baseline fixture run:

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar_cm2_loop python3 -m apps.jobs.runner manual_seed --limit 12
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar_cm2_loop python3 -m apps.jobs.runner m3
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar_cm2_loop python3 -m apps.jobs.runner daily_brief
```

Baseline results:

- Manual seed: 12 fetched, 12 persisted, 0 rejected.
- M3 analytics: 32 opportunity rows persisted.
- First brief status: `initial_snapshot`.
- First brief counts: `changed_operators=8`, `new_signals=0`, `opportunity_movement=0`, `new_reachable_leads=8`, `top_actions=3`.
- Opportunity movement is intentionally `0` on first run because score movement requires at least two analytics/brief snapshots.

Changed fixture applied after the first brief:

- Added source-backed planned operator `Kitsilano Recovery Lab` from `city_vancouver_business_licences`.
- Added source-backed public website contact for that operator.
- Added source-backed official high-severity recall signal from `health_canada_recalls`.
- Raised backed scorecard `score_recovery_contrast_therapy_5915022` from `0.8118` to `0.9118`.

Second brief generation:

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar_cm2_loop python3 -m apps.jobs.runner daily_brief
```

Second brief counts:

```json
{
  "changed_operators": 1,
  "new_signals": 1,
  "opportunity_movement": 1,
  "new_reachable_leads": 1,
  "top_actions": 3,
  "window_hours": 0.015,
  "had_prior_brief": true,
  "had_prior_opportunity_snapshot": true
}
```

Actual second brief text:

```text
Daily Market Brief - 2026-06-22
Window: 2026-06-22 18:42 to 2026-06-22 18:43 UTC.
Material source-backed changes were detected across 4 brief section(s).

Top actions:
1. Scout Vancouver for recovery and contrast therapy - Opportunity score is rising and 1 newly reachable lead(s) appeared.
2. Review recall signal - Health Canada recall notice for recovery device fixture: Official fixture recall signal for a recovery device category.
3. Track planned opening: Kitsilano Recovery Lab - recovery and contrast therapy operator surfaced in Kitsilano; status is planned.

Change counts:
- Changed operators: 1
- New high-trust signals: 1
- Opportunity movements: 1
- New reachable leads: 1

Changed operators:
- Planned operator: Kitsilano Recovery Lab - recovery and contrast therapy operator surfaced in Kitsilano; status is planned.

New high-trust signals:
- Health Canada recall notice for recovery device fixture - Official fixture recall signal for a recovery device category.

Opportunity movement:
- Vancouver recovery and contrast therapy gap - recovery and contrast therapy in Vancouver is rising at 0.91 (+0.10 vs prior snapshot).

New reachable leads:
- New reachable lead: Kitsilano Recovery Lab - Kitsilano Recovery Lab gained public website data (1 contact row(s)).
```

Provenance check from the persisted second brief:

- Top action 1 cited `opportunity_movement` and `new_reachable_leads` evidence rows with 13 aggregate source refs.
- Top action 2 cited the `new_signals` row with 1 source ref.
- Top action 3 cited the `changed_operators` row with 1 source ref.
- Every displayed section item had at least one `source_refs` entry.

API checks against the clean fixture DB:

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar_cm2_loop uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8001
curl -s http://127.0.0.1:8001/api/brief
curl -s http://127.0.0.1:8001/api/brief/2026-06-22
```

Results:

- `/api/brief` returned the latest brief with sections, 3 actions, counts, and provenance.
- `/api/brief/2026-06-22` returned the same date-specific brief.
- OpenAPI contained both `/api/brief` and `/api/brief/{brief_date}`.

Empty-day path:

- A third generation with no new source-backed changes returned `status=no_material_changes`.
- Counts were all `0`; `top_actions=[]`.
- Brief text included: `No material source-backed market changes were detected in the comparison window.`

Scheduler/webhook proof:

- Inserted `alert_subscription` with condition `daily_market_brief` and channel `webhook`.
- Dispatched via `dispatch_daily_market_brief(..., provider=WebhookAlertProvider('http://127.0.0.1:8002/hook'))`.
- Local webhook sink received condition `daily_market_brief`.
- `alert_dispatch` recorded `status=delivered` and payload delivery status `delivered`.

### CM2 Commands Run

```bash
python3 -m pytest -q
python3 -m ruff check .
python3 -m mypy apps packages db
pnpm lint
pnpm typecheck
pnpm test
pnpm build
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar_cm2_loop python3 -m db.migrate
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar_cm2_loop python3 -m apps.jobs.runner manual_seed --limit 12
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar_cm2_loop python3 -m apps.jobs.runner m3
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar_cm2_loop python3 -m apps.jobs.runner daily_brief
curl -s http://127.0.0.1:8001/api/brief
curl -s http://127.0.0.1:8001/api/brief/2026-06-22
```

Results:

- Python tests: 57 passed.
- Ruff: passed.
- Mypy: passed.
- Web lint/typecheck: passed.
- Web unit tests: 9 passed.
- Web build: passed; Vite still reports the existing large chunk warning.

## R2 — Map

Scope: frontend only. The home/Console route is now a places-first map surface
with a ranked bundle rail and selected-bundle detail panel.

- Basemap source: MapLibre GL renders the free, no-key OpenFreeMap Liberty
  vector style at `https://tiles.openfreemap.org/styles/liberty`; map
  attribution remains enabled.
- Pins and clustering render from `GET /operators`. Source-backed operators
  inside the Metro Vancouver client bounds become clustered map pins; clicking a
  cluster zooms in, and clicking a pin opens a popup with name, category or
  selected bundle, address, status, and public contact links.
- Bundle cards render from `GET /bundles`. Selecting a bundle filters the map
  to `GET /bundles/{id}` members, frames those pins, and shows the bundle score
  components, geography rows, and top people with why-they-appear text.
- Operators lacking usable lat/lng are omitted from the map and counted in the
  bundle rail/coverage panel. The UI still requires source refs before display.

## R1 — Bundles

Scope: backend/API only. Added deterministic bundle synthesis from canonical operator
data, raw OSM/source subtype tags, and source-backed name/category text. The taxonomy
lives in `apps/jobs/analytics/bundles.py` and is extensible by adding bundle definitions;
membership is still data-driven because operators join only when their stored categories,
raw subtype tags, or name text match.

Migration: `012_bundles.sql`

Real run:

```bash
python3 -m db.migrate
python3 -m apps.jobs.runner bundle_synthesis
```

Result:

```text
applied migration 012_bundles.sql
{'fetched': 357, 'persisted': 224, 'rejected': 0, 'errors': 0}
```

Clean DB migration check:

```text
applied migration 001_canonical_schema.sql
applied migration 002_source_registry_seed.sql
applied migration 003_m2_private_alpha.sql
applied migration 004_m3_intelligence_beta.sql
applied migration 005_m4_production_hardening.sql
applied migration 006_scheduler_alert_delivery.sql
applied migration 007_contacts_deal_flow.sql
applied migration 008_daily_brief.sql
applied migration 009_cm3_neighborhood_propositions.sql
applied migration 010_cm4_brief_proposition_exports.sql
applied migration 011_cm5_live_demand_neighborhood_assignment.sql
applied migration 012_bundles.sql
```

Endpoint: `GET /bundles?limit=20`

```json
[
  {
    "id": "bundle_allied_health_bodywork",
    "label": "Allied health & bodywork",
    "score": 0.7828,
    "member_count": 89,
    "confidence": 0.843,
    "top_geo": [
      {"geo_level": "CSD", "geo_name": "Vancouver", "member_count": 68, "population": 662248.0, "density": 1.0268},
      {"geo_level": "neighborhood", "geo_name": "Downtown", "member_count": 30, "population": null, "density": null},
      {"geo_level": "neighborhood", "geo_name": "Fairview", "member_count": 11, "population": null, "density": null}
    ]
  },
  {
    "id": "bundle_boutique_strength",
    "label": "Boutique strength",
    "score": 0.731,
    "member_count": 31,
    "confidence": 0.787,
    "top_geo": [
      {"geo_level": "CSD", "geo_name": "Vancouver", "member_count": 12, "population": 662248.0, "density": 0.1812},
      {"geo_level": "neighborhood", "geo_name": "Downtown", "member_count": 5, "population": null, "density": null},
      {"geo_level": "neighborhood", "geo_name": "Kitsilano", "member_count": 2, "population": null, "density": null}
    ]
  },
  {
    "id": "bundle_longevity_iv",
    "label": "Longevity / IV",
    "score": 0.7086,
    "member_count": 20,
    "confidence": 0.7849,
    "top_geo": [
      {"geo_level": "CSD", "geo_name": "Vancouver", "member_count": 10, "population": 662248.0, "density": 0.151},
      {"geo_level": "neighborhood", "geo_name": "Downtown", "member_count": 9, "population": null, "density": null},
      {"geo_level": "CSD", "geo_name": "Richmond", "member_count": 2, "population": 209937.0, "density": 0.0953}
    ]
  },
  {
    "id": "bundle_spa_thermal",
    "label": "Spa & thermal",
    "score": 0.6959,
    "member_count": 27,
    "confidence": 0.8107,
    "top_geo": [
      {"geo_level": "CSD", "geo_name": "Vancouver", "member_count": 16, "population": 662248.0, "density": 0.2416},
      {"geo_level": "neighborhood", "geo_name": "Downtown", "member_count": 8, "population": null, "density": null},
      {"geo_level": "CSD", "geo_name": "Burnaby", "member_count": 3, "population": 249125.0, "density": 0.1204}
    ]
  },
  {
    "id": "bundle_social_wellness_clubs",
    "label": "Social wellness clubs",
    "score": 0.6826,
    "member_count": 15,
    "confidence": 0.8113,
    "top_geo": [
      {"geo_level": "CSD", "geo_name": "Vancouver", "member_count": 9, "population": 662248.0, "density": 0.1359},
      {"geo_level": "neighborhood", "geo_name": "Downtown", "member_count": 3, "population": null, "density": null},
      {"geo_level": "CSD", "geo_name": "Burnaby", "member_count": 2, "population": 249125.0, "density": 0.0803}
    ]
  },
  {
    "id": "bundle_cold_plunge_contrast_therapy",
    "label": "Cold plunge & contrast therapy",
    "score": 0.6729,
    "member_count": 14,
    "confidence": 0.8066,
    "top_geo": [
      {"geo_level": "CSD", "geo_name": "Vancouver", "member_count": 11, "population": 662248.0, "density": 0.1661},
      {"geo_level": "neighborhood", "geo_name": "Downtown", "member_count": 4, "population": null, "density": null},
      {"geo_level": "neighborhood", "geo_name": "West End", "member_count": 2, "population": null, "density": null}
    ]
  },
  {
    "id": "bundle_yoga_pilates",
    "label": "Yoga & pilates",
    "score": 0.6463,
    "member_count": 9,
    "confidence": 0.756,
    "top_geo": [
      {"geo_level": "CSD", "geo_name": "Vancouver", "member_count": 3, "population": 662248.0, "density": 0.0453},
      {"geo_level": "neighborhood", "geo_name": "Downtown", "member_count": 3, "population": null, "density": null},
      {"geo_level": "neighborhood", "geo_name": "West End", "member_count": 1, "population": null, "density": null}
    ]
  }
]
```

Endpoint: `GET /bundles/bundle_cold_plunge_contrast_therapy`

Source refs below are abbreviated to `source_name`, `source_record_id`, and
`trust_tier`; the API returns full source ref objects.

```json
{
  "id": "bundle_cold_plunge_contrast_therapy",
  "label": "Cold plunge & contrast therapy",
  "bundle_score": 0.6729,
  "confidence_score": 0.8066,
  "member_count": 14,
  "components": {
    "demand_proxy": 0.9906,
    "member_scale": 0.6018,
    "low_supply_density": 0.7164,
    "momentum": 0.1573,
    "source_confidence": 0.8066,
    "formula": "0.30 demand_proxy + 0.20 member_scale + 0.20 low_supply_density + 0.20 momentum + 0.10 source_confidence",
    "methodology_version": "r1_bundle_synthesis_v1",
    "inputs": {
      "member_count": 14,
      "bundle_density_per_10000_population": 0.1444,
      "new_members_90d": 14,
      "new_members_180d": 14,
      "signal_velocity_90d": 14,
      "signal_velocity_180d": 14,
      "momentum_index": 31.5
    }
  },
  "geography": {
    "bundle_density_per_10000_population": 0.1444,
    "demand_proxy": 0.9906,
    "concentrations": [
      {"geo_level": "CSD", "geo_name": "Vancouver", "member_count": 11, "population": 662248.0, "density": 0.1661},
      {"geo_level": "neighborhood", "geo_name": "Downtown", "member_count": 4, "population": null, "density": null},
      {"geo_level": "neighborhood", "geo_name": "West End", "member_count": 2, "population": null, "density": null},
      {"geo_level": "CSD", "geo_name": "North Vancouver", "member_count": 1, "population": 58120.0, "density": 0.1721},
      {"geo_level": "CSD", "geo_name": "Burnaby", "member_count": 1, "population": 249125.0, "density": 0.0401}
    ]
  },
  "members": [
    {
      "id": "op_manual_seed_art_of_sauna",
      "name": "Art of Sauna",
      "municipality": "Burnaby",
      "neighborhood": "Edmonds",
      "lat": 49.2202925,
      "lng": -122.9289587,
      "website": "https://artofsauna.ca/",
      "contacts": [{"contact_type": "website", "value": "https://artofsauna.ca/"}],
      "match_reasons": {"category_matches": ["recovery_contrast_therapy"], "keyword_matches": ["contrast", "recovery", "sauna"], "tag_matches": []},
      "source_refs": [{"source_name": "manual_seed", "source_record_id": "art_of_sauna", "trust_tier": "informal"}]
    },
    {
      "id": "op_manual_seed_aetherhaus",
      "name": "AetherHaus",
      "municipality": "Vancouver",
      "neighborhood": "West End",
      "lat": 49.2869063,
      "lng": -123.1415786,
      "website": "https://www.aetherhaus.ca/",
      "contacts": [{"contact_type": "website", "value": "https://www.aetherhaus.ca/"}],
      "match_reasons": {"category_matches": ["recovery_contrast_therapy"], "keyword_matches": ["contrast", "recovery"], "tag_matches": []},
      "source_refs": [{"source_name": "manual_seed", "source_record_id": "aetherhaus", "trust_tier": "informal"}]
    },
    {
      "id": "op_manual_seed_kolm_kontrast",
      "name": "Kolm Kontrast",
      "municipality": "Vancouver",
      "neighborhood": "Fairview",
      "lat": 49.2642,
      "lng": -123.116,
      "website": "https://www.kolmkontrast.com/",
      "contacts": [{"contact_type": "website", "value": "https://www.kolmkontrast.com/"}],
      "match_reasons": {"category_matches": ["recovery_contrast_therapy"], "keyword_matches": ["contrast", "kontrast", "recovery"], "tag_matches": []},
      "source_refs": [{"source_name": "manual_seed", "source_record_id": "kolm_kontrast", "trust_tier": "informal"}]
    },
    {
      "id": "op_manual_seed_tality_mount_pleasant",
      "name": "Tality Wellness Mount Pleasant",
      "municipality": "Vancouver",
      "neighborhood": "Mount Pleasant",
      "lat": 49.2676,
      "lng": -123.1018,
      "website": "https://www.talitywellness.ca/",
      "contacts": [{"contact_type": "website", "value": "https://www.talitywellness.ca/"}],
      "match_reasons": {"category_matches": ["recovery_contrast_therapy"], "keyword_matches": ["contrast", "recovery"], "tag_matches": []},
      "source_refs": [{"source_name": "manual_seed", "source_record_id": "tality_mount_pleasant", "trust_tier": "informal"}]
    },
    {
      "id": "op_manual_seed_tality_kitsilano",
      "name": "Tality Wellness Kitsilano",
      "municipality": "Vancouver",
      "neighborhood": "Kitsilano",
      "lat": 49.2641,
      "lng": -123.1858,
      "website": "https://www.talitywellness.ca/",
      "contacts": [{"contact_type": "website", "value": "https://www.talitywellness.ca/"}],
      "match_reasons": {"category_matches": ["recovery_contrast_therapy"], "keyword_matches": ["contrast", "recovery"], "tag_matches": []},
      "source_refs": [{"source_name": "manual_seed", "source_record_id": "tality_kitsilano", "trust_tier": "informal"}]
    },
    {
      "id": "op_manual_seed_tality_shipyards",
      "name": "Tality Wellness Shipyards",
      "municipality": "North Vancouver",
      "neighborhood": "Lower Lonsdale",
      "lat": 49.3097,
      "lng": -123.0803,
      "website": "https://www.talitywellness.ca/",
      "contacts": [{"contact_type": "website", "value": "https://www.talitywellness.ca/"}],
      "match_reasons": {"category_matches": ["recovery_contrast_therapy"], "keyword_matches": ["contrast", "recovery"], "tag_matches": []},
      "source_refs": [{"source_name": "manual_seed", "source_record_id": "tality_shipyards", "trust_tier": "informal"}]
    },
    {
      "id": "op_osm_overpass_node_3746143481",
      "name": "F212",
      "municipality": "Vancouver",
      "neighborhood": "West End",
      "lat": 49.2797986,
      "lng": -123.130533,
      "website": "https://f212.com/",
      "contacts": [{"contact_type": "email", "value": "info@f212.com"}, {"contact_type": "phone", "value": "+1-604-689-9719"}, {"contact_type": "website", "value": "https://f212.com/"}],
      "match_reasons": {"category_matches": ["recovery_contrast_therapy"], "keyword_matches": ["contrast", "recovery", "sauna"], "tag_matches": ["leisure=sauna"]},
      "source_refs": [{"source_name": "osm_overpass", "source_record_id": "node/3746143481", "trust_tier": "community"}]
    },
    {
      "id": "op_manual_seed_orijin_restore",
      "name": "Orijin Restore",
      "municipality": "Vancouver",
      "neighborhood": "Renfrew-Collingwood",
      "lat": 49.2327,
      "lng": -123.0247,
      "website": "https://orijinrestore.com/",
      "contacts": [{"contact_type": "website", "value": "https://orijinrestore.com/"}],
      "match_reasons": {"category_matches": ["recovery_contrast_therapy"], "keyword_matches": ["contrast", "recovery", "restore"], "tag_matches": []},
      "source_refs": [{"source_name": "manual_seed", "source_record_id": "orijin_restore", "trust_tier": "informal"}]
    },
    {
      "id": "op_manual_seed_regen_recovery",
      "name": "Regen Recovery",
      "municipality": "Vancouver",
      "neighborhood": "Kensington-Cedar Cottage",
      "lat": 49.2565,
      "lng": -123.074,
      "website": "https://www.regenrecovery.ca/",
      "contacts": [{"contact_type": "website", "value": "https://www.regenrecovery.ca/"}],
      "match_reasons": {"category_matches": ["recovery_contrast_therapy"], "keyword_matches": ["contrast", "recovery"], "tag_matches": []},
      "source_refs": [{"source_name": "manual_seed", "source_record_id": "regen_recovery", "trust_tier": "informal"}]
    },
    {
      "id": "op_osm_overpass_node_3036583989",
      "name": "Floathouse - Gastown",
      "municipality": "Vancouver",
      "neighborhood": "Downtown",
      "lat": 49.2826851,
      "lng": -123.1062671,
      "website": "https://floathouse.ca/",
      "contacts": [{"contact_type": "phone", "value": "+1-604-253-5628"}, {"contact_type": "website", "value": "https://floathouse.ca/"}],
      "match_reasons": {"category_matches": ["recovery_contrast_therapy"], "keyword_matches": ["contrast", "float", "recovery"], "tag_matches": []},
      "source_refs": [{"source_name": "osm_overpass", "source_record_id": "node/3036583989", "trust_tier": "community"}]
    },
    {
      "id": "op_manual_seed_fairmont_pacific_rim_spa",
      "name": "Fairmont Pacific Rim Spa",
      "municipality": "Vancouver",
      "neighborhood": "Downtown",
      "lat": 49.288,
      "lng": -123.1164,
      "website": "https://www.fairmont-pacific-rim.com/spa/",
      "contacts": [{"contact_type": "website", "value": "https://www.fairmont-pacific-rim.com/spa/"}],
      "match_reasons": {"category_matches": ["recovery_contrast_therapy"], "keyword_matches": ["contrast", "recovery"], "tag_matches": []},
      "source_refs": [{"source_name": "manual_seed", "source_record_id": "fairmont_pacific_rim_spa", "trust_tier": "informal"}]
    },
    {
      "id": "op_manual_seed_bugu_wellness",
      "name": "Bugu Wellness",
      "municipality": "Port Coquitlam",
      "neighborhood": "Central Port Coquitlam",
      "lat": 49.262,
      "lng": -122.7811,
      "website": "https://www.buguwellness.com/",
      "contacts": [{"contact_type": "website", "value": "https://www.buguwellness.com/"}],
      "match_reasons": {"category_matches": ["recovery_contrast_therapy"], "keyword_matches": ["contrast", "recovery"], "tag_matches": []},
      "source_refs": [{"source_name": "manual_seed", "source_record_id": "bugu_wellness", "trust_tier": "informal"}]
    },
    {
      "id": "op_manual_seed_sea2sky_sauna",
      "name": "Sea2Sky Sauna",
      "municipality": "Vancouver",
      "neighborhood": "Downtown",
      "lat": 49.2827,
      "lng": -123.1207,
      "website": "https://www.sea2skysauna.ca/",
      "contacts": [{"contact_type": "website", "value": "https://www.sea2skysauna.ca/"}],
      "match_reasons": {"category_matches": ["recovery_contrast_therapy"], "keyword_matches": ["contrast", "recovery", "sauna"], "tag_matches": []},
      "source_refs": [{"source_name": "manual_seed", "source_record_id": "sea2sky_sauna", "trust_tier": "informal"}]
    },
    {
      "id": "op_manual_seed_ritual_urban_retreat",
      "name": "Ritual Urban Retreat",
      "municipality": "Vancouver",
      "neighborhood": "Downtown",
      "lat": 49.2827,
      "lng": -123.1207,
      "website": "https://www.ritualurbanretreat.com/",
      "contacts": [{"contact_type": "website", "value": "https://www.ritualurbanretreat.com/"}],
      "match_reasons": {"category_matches": ["recovery_contrast_therapy"], "keyword_matches": ["contrast", "recovery"], "tag_matches": []},
      "source_refs": [{"source_name": "manual_seed", "source_record_id": "ritual_urban_retreat", "trust_tier": "informal"}]
    }
  ],
  "top_people": [
    {
      "id": "person_aetherhaus_team",
      "name": "AetherHaus Team",
      "rank": 1,
      "influence_score": 0.2158,
      "why_appears": "Public operator team at AetherHaus links this person to Cold plunge & contrast therapy; influence score 0.22.",
      "source_refs": [
        {"source_name": "manual_people_csv", "source_record_id": "aetherhaus_team", "trust_tier": "informal"},
        {"source_name": "manual_seed", "source_record_id": "aetherhaus", "trust_tier": "informal"},
        {"source_name": "bundle_synthesis_taxonomy", "source_record_id": "r1_bundle_synthesis_v1", "trust_tier": "informal"}
      ]
    }
  ],
  "supporting_signals": [
    {"id": "sig_osm_overpass_node_3746143481_operator_observed", "title": "OSM wellness POI observed: F212", "related_operator_id": "op_osm_overpass_node_3746143481", "source_refs": [{"source_name": "osm_overpass", "source_record_id": "node/3746143481", "trust_tier": "community"}]},
    {"id": "sig_osm_overpass_node_3036583989_operator_observed", "title": "OSM wellness POI observed: Floathouse - Gastown", "related_operator_id": "op_osm_overpass_node_3036583989", "source_refs": [{"source_name": "osm_overpass", "source_record_id": "node/3036583989", "trust_tier": "community"}]},
    {"id": "sig_manual_seed_fairmont_pacific_rim_spa_operator_seed", "title": "Manual recovery seed: Fairmont Pacific Rim Spa", "related_operator_id": "op_manual_seed_fairmont_pacific_rim_spa", "source_refs": [{"source_name": "manual_seed", "source_record_id": "fairmont_pacific_rim_spa", "trust_tier": "informal"}]}
  ],
  "source_refs": [
    {"source_name": "bundle_synthesis_taxonomy", "source_record_id": "r1_bundle_synthesis_v1", "trust_tier": "informal"},
    {"source_name": "manual_seed", "source_record_id": "art_of_sauna", "trust_tier": "informal"},
    {"source_name": "manual_seed", "source_record_id": "aetherhaus", "trust_tier": "informal"},
    {"source_name": "manual_seed", "source_record_id": "kolm_kontrast", "trust_tier": "informal"}
  ]
}
```

### R1 Commands Run

```bash
python3 -m db.migrate
python3 -m apps.jobs.runner bundle_synthesis
python3 -m pytest -q
python3 -m ruff check .
python3 -m mypy .
pnpm build
```

Results:

- Bundle synthesis real run: fetched 357, persisted 224, rejected 0, errors 0.
- `GET /bundles?limit=20`: 200, returned 7 ranked bundles.
- `GET /bundles/bundle_cold_plunge_contrast_therapy`: 200, returned score, geography, 14 members, 1 top person, and supporting signals.
- Python tests: 69 passed.
- Ruff: passed.
- Mypy: passed.
- Clean DB migration: `001` through `012` applied successfully in a throwaway database.
- Web build: passed; Vite still reports the existing large chunk warning.
- Clean migration applied through `008`.
- Ops alert tests still pass, including existing source-stale/adapter-failure dispatch behavior.

## CM3 Neighborhood Gaps + Propositions

### What Changed

- Added migration `009_cm3_neighborhood_propositions.sql`.
- Opportunity analytics now writes both `geo_level='CSD'` and `geo_level='neighborhood'` cells.
- Neighborhood cells are derived from source-backed operator `neighborhood` tags and BC-gated centroids.
- Each cell carries raw demand fields in `trace_payload`: `raw_population`, `raw_business_count`, demand source/status, radius competitor count, and parent-CSD allocation metadata when used.
- Added deterministic proposition synthesis in `apps/jobs/analytics/propositions.py`.
- Added `GET /api/propositions` and `geo_level` filtering for `/analytics/whitespace` and scorecards.
- Daily brief top actions now prefer neighborhood propositions when available.
- Frontend Opportunity screen now switches `Neighborhood` / `CSD` and lists written propositions with evidence and source links.

### Real CM3 Run Evidence

Commands run against local Postgres:

```bash
python3 -m db.migrate
python3 -m apps.jobs.runner manual_seed --limit 100
python3 -m apps.jobs.runner statcan_denominators
python3 -m apps.jobs.runner opportunity_analytics
python3 -m apps.jobs.runner proposition_synthesis
python3 -m apps.jobs.runner daily_brief
```

Persisted heatmap counts:

```text
CSD allied_health: 5
CSD fitness_movement: 5
CSD recovery_contrast_therapy: 5
CSD spa_thermal: 5
neighborhood allied_health: 17
neighborhood fitness_movement: 4
neighborhood recovery_contrast_therapy: 10
neighborhood spa_thermal: 8
```

Sample neighborhood cell:

```json
{
  "category": "recovery_contrast_therapy",
  "geo_name": "Downtown",
  "geo_level": "neighborhood",
  "supply_count": 3,
  "population": 180613.090909091,
  "business_count": 70.9090909090909,
  "opportunity_score": 0.5133,
  "confidence_score": 0.5621143,
  "competitor_count_within_radius": 11,
  "competitor_radius_km": 4,
  "demand_source": "statcan_wds_fixture",
  "demand_source_status": "fixture_fallback",
  "raw_parent_population": 662248
}
```

Sample proposition from `/api/propositions?category=recovery_contrast_therapy&geo_level=neighborhood&limit=2`:

```json
{
  "headline": "Open recovery and contrast therapy in Edmonds",
  "geo_level": "neighborhood",
  "geo_name": "Edmonds",
  "category": "recovery_contrast_therapy",
  "competitor_count_within_radius": 1,
  "competitor_radius_km": 4,
  "population": 249125,
  "business_count": 74,
  "opportunity_score": 0.5133,
  "confidence": 0.6784,
  "demand_source": "statcan_wds_fixture",
  "summary": "Open recovery and contrast therapy in Edmonds: 1 competitor(s) within 4 km; 249,125 people estimated neighborhood population from 100.0% share of Burnaby (249,125 people); 74 business locations estimated category business count from parent CSD raw count 74 business locations. Opportunity score is 0.51 with 0.68 confidence; demand source is fixture_fallback."
}
```

Daily brief proof:

- `top_propositions`: 8.
- Top action after CM3 ordering: `Evaluate proposition: Open recovery and contrast therapy in Downtown`.
- Summary includes 11 competitors within 4 km, estimated neighborhood population, parent-CSD raw population/business counts, and `fixture_fallback` demand provenance.

### Demand Source Status

- Live StatCan WDS was attempted in `auto` mode.
- The local run could not complete the live WDS handshake: `_ssl.c:990: The handshake operation timed out`.
- The recorded StatCan denominator fixture was used with explicit provenance:
  - `demand_source='statcan_wds_fixture'`
  - `demand_source_status='fixture_fallback'`
  - `live_attempted=true`
  - `live_error` persisted in denominator payloads.
- Neighborhood denominator values are transparent parent-CSD allocations where no official neighborhood denominator exists. Confidence is reduced for fixture-backed and allocated demand.
- Peer-city trends remain `is_stub=true` and are not presented as live demand.

### CM3 Commands Run

```bash
python3 -m db.migrate
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar_cm3_clean python3 -m db.migrate
python3 -m apps.jobs.runner manual_seed --limit 100
python3 -m apps.jobs.runner statcan_denominators
python3 -m apps.jobs.runner opportunity_analytics
python3 -m apps.jobs.runner proposition_synthesis
python3 -m apps.jobs.runner daily_brief
python3 - <<'PY'
from fastapi.testclient import TestClient
from apps.api.app.main import app
client = TestClient(app)
print(client.get('/api/propositions?category=recovery_contrast_therapy&geo_level=neighborhood&limit=2').status_code)
print(client.get('/analytics/whitespace?category=recovery_contrast_therapy&geo_level=neighborhood&limit=2').status_code)
PY
pytest
ruff check .
mypy .
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

Results:

- Python tests: 59 passed.
- Ruff: passed.
- Mypy: passed.
- Web lint/typecheck: passed.
- Web unit tests: 9 passed.
- Web build: passed; Vite still reports the existing large chunk warning.
- Clean migration applied through `009`.
- Docker-based compose verification was not possible in this session because access to `/var/run/docker.sock` was denied; local Postgres migration/job/API verification was completed instead.

## Final Status

### Production Gate

- Freshness monitor live: met. `/admin/source-freshness` and `/admin/observability` report source age/SLA status.
- Adapter failure alerts live: met for evaluation and in-app/stub dispatch. External notification delivery remains a production integration.
- RBAC in place: met. Protected admin/write endpoints require role tokens.
- Source-rights registry complete: matrix is complete and reviewed where possible; public production is blocked for sources still marked `needs_review`.
- Public people scoring correction workflow: met at API/schema/audit/docs level; human owner and response SLA remain required before public launch.
- Export/snapshot working: met for operators, signals, and graph in CSV/JSON plus persisted snapshots.

### M0-M4 Checklist

- M0 Repo harness: done.
- M1 BC-only vertical slice: done.
- M2 MVP private alpha: done.
- M3 Intelligence beta: done, with fixture-backed peer-city trends clearly labelled.
- M4 Production hardening: done for build scope, with honest production/human-review gaps listed above.
- CM1 Contacts/deal-flow layer: done.
- CM2 Daily market-intelligence brief: done.
- CM3 Neighborhood gaps/propositions: done, with fixture-backed demand clearly labelled.

### Run The Whole System

```bash
sudo -n docker compose up --build -d
```

Then open:

- `http://localhost:5173`
- `http://localhost:5173?mode=kiosk`
- `http://localhost:8000/health`
- `http://localhost:8000/metrics`

Protected local admin examples:

```bash
curl -s -H 'Authorization: Bearer local-analyst-token' http://127.0.0.1:8000/admin/observability
curl -s -H 'Authorization: Bearer local-analyst-token' http://127.0.0.1:8000/admin/alerts/evaluate
```

### Final Test Count

- Python: 59 passing.
- Web: 9 passing.
- Total: 68 passing.

### Remaining Gaps Before Public Production

- Complete human legal/source-rights review for all remaining `needs_review` sources, especially enabled manual, OSM, OrgBook, RSS, and fixture trend sources.
- Replace fixture peer-city trends with a reviewed provider or keep the non-live label permanently.
- Add reviewed CRE inputs only after source rights and field allowlists are approved.
- Configure real deployment secrets, external alert dispatch, monitoring sinks, and incident ownership outside the repo.
- Assign a public correction workflow owner and SLA before exposing people scoring publicly.
- Decide whether production uses the in-repo scheduler loop or an external orchestrator for daily brief and ingest cadence ownership.

## CM4 Close-Out - Brief Fire, Written Propositions, Coverage

### Summary

- Daily briefs are now idempotent per calendar day. Today's brief regenerates in place, compares against the latest prior-day brief, and always covers at least 24 hours even when a brief was generated minutes ago.
- Clean runs backfill recent brief history from existing source/operator/signal/proposition timestamps. `GET /api/brief/{date}` returns persisted historical briefs, and `GET /api/brief/recent?limit=N` plus `GET /api/brief?limit=N` list recent briefs.
- Opportunity propositions now run across all lead-wedge categories present in the data, not only `recovery_contrast_therapy`, and include written thesis fields, market sizing, named nearest competitors, source refs, and confidence narratives.
- Leads are joinable to neighborhoods, lead contacts serialize `contact_type`, public leads CSV export works through `Accept: text/csv` or `?format=csv`, and `/people?limit=500` clamps instead of returning 400.
- People records now expose `contacts: []`, `contactable: false` when no public direct contact is present, and `person_type` values such as `policy_figure`, `operator`, and `public_professional`.

### Clean DB Verification

Clean database: `wellness_radar_cm4_clean`

Commands:

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar_cm4_clean python3 -m db.migrate
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar_cm4_clean WR_STATCAN_WDS_MODE=fixture python3 -m apps.jobs.runner cm3 --limit 20
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar_cm4_clean uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8014
```

Migration applied through `010_cm4_brief_proposition_exports.sql`.

Runner result highlights:

- `daily_brief`: `status=initial_snapshot`, `top_actions=3`, `window_hours=72.0`, `minimum_window_hours=24`, `top_propositions=8`, `changed_operators=8`, `new_signals=8`, `new_reachable_leads=8`.
- Backfilled history: `2026-06-17`, `2026-06-19`, `2026-06-22`.
- Proposition synthesis: 41 written propositions persisted from 41 opportunity score snapshots.

### Populated Brief Proof

Endpoint: `GET /api/brief`

```json
{
  "brief_date": "2026-06-22",
  "status": "initial_snapshot",
  "window_start": "2026-06-19T19:48:50.678344+00:00",
  "window_end": "2026-06-22T19:48:50.678344+00:00",
  "counts": {
    "new_signals": 8,
    "top_actions": 3,
    "window_hours": 72.0,
    "had_prior_brief": true,
    "top_propositions": 8,
    "changed_operators": 8,
    "new_reachable_leads": 8,
    "minimum_window_hours": 24,
    "opportunity_movement": 0,
    "had_prior_opportunity_snapshot": false
  }
}
```

Real populated top actions:

1. `Evaluate proposition: Edmonds: source-backed spa and thermal whitespace`
   - Market sizing proxy: 249,125 people x $215 per-person StatCan personal care service household spend proxy = $53.5M broad annual addressable spend.
   - Named competitors within 4 km: Art of Sauna, Queens Park Massage Therapy.
   - Confidence narrative: confidence 0.36; base score confidence 0.67; demand denominator is fixture-backed; neighborhood values are allocated from parent CSD denominators; spend proxy is broad; 2 named/countable competitor inputs.
   - Source refs include StatCan WDS/profile, StatCan personal care spend, BC average household size, Art of Sauna, and OSM node 961847328.
2. `Evaluate proposition: Edmonds: source-backed recovery and contrast therapy whitespace`
   - Market sizing proxy: 249,125 people x $2,180 per-person StatCan 2023 recreation household spend proxy = $543.0M broad annual addressable spend.
   - Named competitor within 4 km: Art of Sauna.
   - Confidence narrative: confidence 0.40; base score confidence 0.68; fixture-backed denominator; allocated neighborhood values; broad StatCan recreation proxy; 1 named/countable competitor input.
   - Source refs include StatCan WDS/profile, StatCan 2023 household recreation spend, BC average household size, and Art of Sauna.
3. `Evaluate proposition: Downtown: source-backed spa and thermal whitespace`
   - Market sizing proxy: 165,562 people x $215 per-person StatCan personal care service household spend proxy = $35.5M broad annual addressable spend.
   - Named competitors within 4 km: Ritual Urban Retreat, Vancouver Chiropractor, Massage therapy clinic, Davie Registered Massage Therapy Corner, Fairmont Pacific Rim Spa, AetherHaus.
   - Confidence narrative: confidence 0.32; base score confidence 0.60; fixture-backed denominator; allocated neighborhood values; broad StatCan personal care service proxy; 5 named/countable competitor inputs.

Brief history endpoint: `GET /api/brief/recent?limit=5`

```json
[
  {"brief_date": "2026-06-22", "status": "initial_snapshot", "top_actions": 3, "window_hours": 72.0},
  {"brief_date": "2026-06-19", "status": "initial_snapshot", "top_actions": 0, "window_hours": 72.0},
  {"brief_date": "2026-06-17", "status": "initial_snapshot", "top_actions": 0, "window_hours": 72.0}
]
```

Direct date checks:

- `GET /api/brief/2026-06-22`: 200, `top_actions=3`.
- `GET /api/brief/2026-06-19`: 200, `top_actions=0`.
- `GET /api/brief/2026-06-17`: 200, `top_actions=0`.

### Proposition Examples

Endpoint: `GET /api/propositions?geo_level=neighborhood&limit=25`

Example 1 - `spa_thermal`, Edmonds:

```json
{
  "headline": "Edmonds: source-backed spa and thermal whitespace",
  "market_sizing_line": "Market sizing proxy: 249,125 people x $215 per-person statcan personal care service household spend proxy = $53.5M broad annual addressable spend.",
  "nearest_competitors": ["Art of Sauna", "Queens Park Massage Therapy"],
  "confidence": 0.3594,
  "confidence_narrative": "Confidence 0.36: base score confidence 0.67; demand denominator is fixture-backed; neighborhood values are allocated from parent CSD denominators; spend proxy is broad (StatCan personal care service household spend proxy); 2 named/countable competitor input(s)."
}
```

Example 2 - `allied_health`, Mount Pleasant:

```json
{
  "headline": "Mount Pleasant: source-backed allied health whitespace",
  "market_sizing_line": "Market sizing proxy: 118,259 people x $1,243 per-person cihi out-of-pocket health expenditure per capita proxy = $147.0M broad annual addressable spend.",
  "nearest_competitors": [
    "(Matthew Johnston)",
    "Cedar Pregnancy Care Centre of Vancouver",
    "(Elli Klaus)",
    "(Emma Gerrard)",
    "Ocean Orthodontics",
    "Tall Tee Integrated Health Centre"
  ],
  "confidence": 0.3249,
  "confidence_narrative": "Confidence 0.32: base score confidence 0.63; demand denominator is fixture-backed; neighborhood values are allocated from parent CSD denominators; spend proxy is broad (CIHI out-of-pocket health expenditure per capita proxy); 13 named/countable competitor input(s)."
}
```

Spend proxy source refs used by proposition records:

- StatCan 2023 Survey of Household Spending recreation proxy: `https://www150.statcan.gc.ca/n1/daily-quotidien/250521/dq250521a-eng.htm`
- StatCan personal care service household spend proxy: `https://www.statcan.gc.ca/o1/en/plus/5228-getting-ready-go-out`
- BC average household size conversion: `https://www12.statcan.gc.ca/census-recensement/2021/as-sa/fogs-spg/alternative.cfm?dguid=2021A000259&lang=e&objectId=2&topic=3`
- CIHI out-of-pocket health expenditure proxy: `https://www.cihi.ca/sites/default/files/document/health-expenditure-data-in-brief-2024-en.pdf`

Fixture-backed and allocated demand values remain explicitly labeled and confidence-reduced.

### Leads, Export, People Proof

Endpoint: `GET /leads?limit=3`

```json
[
  {
    "name": "Fitness Town",
    "neighborhood": "Riley Park",
    "contacts": [
      {"contact_type": "phone", "value": "+1-604-322-5988"},
      {"contact_type": "website", "value": "https://fitnesstown.ca/locations-south-vancouver/"}
    ]
  },
  {
    "name": "Vancouver Chiropractor, Massage therapy clinic",
    "neighborhood": "Downtown",
    "contacts": [
      {"contact_type": "phone", "value": "+1-604-688-0724"},
      {"contact_type": "website", "value": "http://www.KilianChiropractic.com"}
    ]
  },
  {
    "name": "Interurban Chiropractic",
    "neighborhood": "Edmonds",
    "contacts": [
      {"contact_type": "phone", "value": "+1-604-553-1550"},
      {"contact_type": "website", "value": "https://interurbanchiropractic.ca/"}
    ]
  }
]
```

Endpoint: `Accept: text/csv GET /leads?limit=2`

```csv
operator_id,operator_name,categories,status,address,municipality,neighborhood,contact_type,contact_value,contact_platform,contact_confidence,contact_source_name,contact_source_url,contact_source_record_id,opportunity_geo_name,opportunity_score,source_refs
op_osm_overpass_node_1686653483,Fitness Town,"[""fitness_movement""]",open,"1306, Southeast Marine Drive, BC",,Riley Park,phone,+1-604-322-5988,,0.76,osm_overpass,https://www.openstreetmap.org/node/1686653483,node/1686653483,Vancouver,0.9415,"[{""licence"": ""Open Database License"", ""seen_at"": ""2026-06-22T19:48:43.499595Z"", ""source_name"": ""osm_overpass"", ""source_record_id"": ""node/1686653483"", ""trust_tier"": ""community"", ""url"": ""https://www.openstreetmap.org/node/1686653483""}]"
```

Endpoint: `GET /people?limit=500`

```json
{
  "meta": {"count": 20, "limit": 250, "requested_limit": 500, "max_limit": 250},
  "first": {
    "name": "Dr. Bonnie Henry",
    "person_type": "policy_figure",
    "contactable": false,
    "contacts": []
  }
}
```

### CM4 Commands Run

```bash
python3 -m pytest -q
python3 -m ruff check .
python3 -m mypy apps packages db
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

Results:

- Python tests: 64 passed.
- Ruff: passed.
- Mypy: passed.
- Web lint/typecheck: passed.
- Web unit tests: 9 passed.
- Web build: passed; Vite still reports the existing large chunk warning.
