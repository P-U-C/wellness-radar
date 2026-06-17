# Vancouver Wellness Radar — Repository Build Specification

**Target repository:** `P-U-C/wellness-radar`  
**Project type:** Metro Vancouver health/wellness market-intelligence console  
**Primary user:** A new entrant/operator evaluating where, when, and how to enter the Metro Vancouver wellness market.  
**Reviewed version:** Pro review pass, June 17, 2026

---

## 0. Pro Review Changes Applied

This version is not a straight copy of the earlier build plan. The following changes were applied to reduce implementation drift and make the repository easier for coding agents to execute:

1. **Repository contract added.** Agents now get a precise repo structure, naming conventions, `CLAUDE.md`, branch rules, issue labels, and acceptance criteria.
2. **Schema clarified.** `operator` and `organization` are split instead of overloading one table. A wellness venue/business is an `operator`; the legal/corporate body is an `organization`.
3. **Source events separated from signals.** `source_event` is the raw normalized event log; `signal` is the user-facing intelligence card derived from one or more source events.
4. **BC geo-filter promoted to package-level gate.** It is now impossible for adapters to persist geo-aware records unless they call the shared `bc_gate`.
5. **Source-rights registry is a hard gate.** No adapter ships without a `source_registry` row and rights notes.
6. **Agent safety model added.** GitHub Actions/Claude automation should work through PRs, limited permissions, tests, and CODEOWNERS; no direct pushes to `main`.
7. **First milestone narrowed.** Phase 0 is only one real vertical slice: City licences → PostGIS → API → MapLibre → entity drawer → source provenance.
8. **Paid APIs deferred by default.** Google Places/Yelp are enrichment, not MVP dependencies, unless the un-geocoded operator rate blocks usefulness.
9. **Map rendering locked to MapLibre + hosted/self-hosted vector tiles.** Do not use OSM community tiles in production.
10. **AI is enrichment, not truth source.** Official data extraction must work deterministically; AI writes `why_it_matters`, tags, and summaries only after provenance exists.
11. **Analytics require explainability.** No opportunity score can render unless component values and source confidence are visible.
12. **People graph governance tightened.** Only public professional data. No private personal attributes, patient inference, LinkedIn scraping, or raw social firehose in MVP.

---

## 1. Product Definition

### 1.1 Product Identity

Build a **map-first, dark-themed opportunity radar** for the Metro Vancouver wellness market.

The dashboard answers four jobs-to-be-done:

1. **Where is the market?**  
   Category-filtered map of wellness operators, facilities, studios, clinics, spas, recovery clubs, and health-adjacent organizations.

2. **What just changed?**  
   Live signal feed of openings, closings, licence changes, inspections, recalls, regulatory changes, hiring, events, funding, and trend spikes.

3. **Who matters?**  
   Influential people and organizations: founders, operators, investors, practitioners, researchers, health-authority figures, creators, and community conveners.

4. **Where/when should we enter?**  
   White-space heatmap and opportunity scoring by category, neighborhood, momentum, and demand proxy.

### 1.2 Strategic Wedge

Lead with the **recovery / contrast therapy / social wellness** category:

- sauna
- cold plunge
- contrast therapy
- recovery clubs
- social bathhouse / community wellness
- longevity-adjacent services

This wedge is narrower and more actionable than “Vancouver health dashboard.” The first demo should show:

> “Here is the live Metro Vancouver recovery-club market: operators, openings, category momentum, influential people, and white-space zones.”

### 1.3 Explicit Non-Goals

Do **not** build:

- patient-data ingestion
- clinical-decision support
- health advice
- EMR / claims / insurer integrations
- patient-level or small-count health data
- private mobility traces
- raw social firehose
- LinkedIn scraping
- unreviewed medical or legal claims

This is a **market-intelligence and public-signal system**, not a healthcare product.

---

## 2. System Architecture

### 2.1 High-Level Flow

```text
Source APIs / feeds / scrapers
        ↓
Source adapters
        ↓
Raw payload storage
        ↓
Normalization
        ↓
BC geo-filter gate
        ↓
Canonical Postgres/PostGIS store
        ↓
Source events
        ↓
Signal generation + AI enrichment
        ↓
FastAPI read API
        ↓
React/MapLibre dashboard widgets
```

### 2.2 Locked Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend | React + TypeScript + Vite | Single-page dashboard |
| Map | MapLibre GL JS via `react-map-gl` | Avoid Mapbox lock-in |
| Tiles | MapTiler or Protomaps | Do not use OSM community tiles in production |
| People graph | Sigma.js + graphology | ForceAtlas2, Louvain, centrality |
| Charts | Recharts or visx | Small trend sparklines |
| Backend API | Python + FastAPI | Read API + admin endpoints |
| Jobs / ETL | Python | Source adapters, scheduled jobs |
| Scheduler | APScheduler for MVP | Queue later if volume warrants |
| Database | PostgreSQL + PostGIS | Canonical store |
| Cache | Redis | Optional in MVP; expected Phase 2 |
| Raw storage | Local dev folder, S3-compatible later | Store source payload snapshots |
| Analytics | Postgres materialized views first | ClickHouse deferred |
| Search | Postgres FTS first | OpenSearch deferred |
| AI | Claude API or compatible LLM provider | Enrichment only |
| Deployment | Vercel/Netlify FE + managed API/job container | Containerized |

### 2.3 Repository Structure

```text
wellness-radar/
  README.md
  CLAUDE.md
  LICENSE
  .env.example
  .gitignore
  docker-compose.yml
  package.json
  pnpm-workspace.yaml
  pyproject.toml

  apps/
    web/
      src/
        app/
        components/
        features/
          map/
          feed/
          entities/
          people/
          analytics/
          admin/
        lib/
        styles/
      tests/
      package.json
      vite.config.ts

    api/
      app/
        main.py
        config.py
        db/
        routers/
          health.py
          operators.py
          signals.py
          people.py
          entities.py
          analytics.py
          admin.py
        services/
        schemas/
      tests/

    jobs/
      runner.py
      scheduler.py
      adapters/
        base.py
        city_vancouver_licences.py
        osm_overpass.py
        orgbook_bc.py
        gdelt.py
        rss.py
        workbc.py
      tests/

  packages/
    schemas/
      canonical.py
      api.py
    geo/
      bc_gate.py
      fixtures/
      tests/
    shared/
      ids.py
      normalizers.py
      provenance.py
      dedupe.py

  db/
    migrations/
    seeds/
    sql/
      views/
      materialized_views/

  infra/
    github/
      workflows/
    docker/
    terraform/          # optional later

  docs/
    adr/
    product/
    data-sources/
    governance/
    runbooks/
```

---

## 3. Data Model

### 3.1 Design Rules

- Every displayed record needs provenance.
- Every source payload is retained or addressable.
- Every fuzzy match has confidence.
- Every entity merge must be reversible or reviewable.
- `source_event` is normalized machine-readable fact/change.
- `signal` is user-facing intelligence generated from one or more source events.

### 3.2 PostgreSQL DDL

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TYPE trust_tier AS ENUM ('official', 'reputable_press', 'commercial_api', 'community', 'informal', 'ai_inferred');
CREATE TYPE operator_status AS ENUM ('open', 'new', 'planned', 'closed', 'rumored', 'unknown');
CREATE TYPE signal_severity AS ENUM ('info', 'notable', 'high');
CREATE TYPE source_run_status AS ENUM ('success', 'partial', 'failed');

CREATE TABLE source_registry (
  source_name       TEXT PRIMARY KEY,
  family            TEXT NOT NULL,
  base_url          TEXT,
  cadence           TEXT NOT NULL,
  licence           TEXT,
  cost              TEXT,
  trust_tier        trust_tier NOT NULL,
  geo_rule          TEXT NOT NULL,
  phase             INT NOT NULL,
  rights_notes      TEXT NOT NULL,
  enabled           BOOLEAN NOT NULL DEFAULT FALSE,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE raw_payload (
  id                TEXT PRIMARY KEY,
  source_name       TEXT NOT NULL REFERENCES source_registry(source_name),
  source_record_id  TEXT,
  fetched_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  content_hash      TEXT NOT NULL,
  storage_uri       TEXT,
  raw_json          JSONB,
  raw_text          TEXT
);

CREATE TABLE source_run (
  id                BIGSERIAL PRIMARY KEY,
  source_name       TEXT NOT NULL REFERENCES source_registry(source_name),
  status            source_run_status NOT NULL,
  started_at        TIMESTAMPTZ NOT NULL,
  completed_at      TIMESTAMPTZ,
  records_fetched   INT NOT NULL DEFAULT 0,
  records_persisted INT NOT NULL DEFAULT 0,
  records_rejected  INT NOT NULL DEFAULT 0,
  error_count       INT NOT NULL DEFAULT 0,
  error_message     TEXT
);

CREATE TABLE rejected_record (
  id                BIGSERIAL PRIMARY KEY,
  source_name       TEXT NOT NULL,
  reason            TEXT NOT NULL,
  raw_payload_id    TEXT,
  raw               JSONB,
  rejected_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE organization (
  id                TEXT PRIMARY KEY,
  name              TEXT NOT NULL,
  normalized_name   TEXT NOT NULL,
  registry_id       TEXT,
  orgbook_id        TEXT,
  organization_type TEXT,
  website           TEXT,
  social_links      JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_refs       JSONB NOT NULL,
  confidence_score  REAL NOT NULL DEFAULT 0.5,
  first_seen_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE operator (
  id                TEXT PRIMARY KEY,
  organization_id   TEXT REFERENCES organization(id),
  name              TEXT NOT NULL,
  normalized_name   TEXT NOT NULL,
  categories        TEXT[] NOT NULL,
  status            operator_status NOT NULL DEFAULT 'unknown',
  address           TEXT,
  municipality      TEXT,
  neighborhood      TEXT,
  health_authority  TEXT,
  phone             TEXT,
  website           TEXT,
  social_links      JSONB NOT NULL DEFAULT '{}'::jsonb,
  geom              GEOGRAPHY(POINT, 4326),
  licence_ref       TEXT,
  orgbook_id        TEXT,
  source_refs       JSONB NOT NULL,
  confidence_score  REAL NOT NULL DEFAULT 0.5,
  first_seen_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE person (
  id                TEXT PRIMARY KEY,
  name              TEXT NOT NULL,
  normalized_name   TEXT NOT NULL,
  roles             TEXT[] NOT NULL DEFAULT '{}',
  affiliations      JSONB NOT NULL DEFAULT '[]'::jsonb,
  public_profiles   JSONB NOT NULL DEFAULT '{}'::jsonb,
  influence_score   REAL,
  locality_score    REAL,
  confidence_score  REAL NOT NULL DEFAULT 0.5,
  source_refs       JSONB NOT NULL,
  first_seen_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE source_event (
  id                TEXT PRIMARY KEY,
  source_name       TEXT NOT NULL REFERENCES source_registry(source_name),
  raw_payload_id    TEXT REFERENCES raw_payload(id),
  source_record_id  TEXT,
  event_type        TEXT NOT NULL,
  entity_type       TEXT,
  entity_id         TEXT,
  title             TEXT,
  occurred_at       TIMESTAMPTZ NOT NULL,
  detected_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  trust_tier        trust_tier NOT NULL,
  geom              GEOGRAPHY(POINT, 4326),
  source_refs       JSONB NOT NULL,
  confidence_score  REAL NOT NULL DEFAULT 0.5,
  payload           JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE signal (
  id                    TEXT PRIMARY KEY,
  type                  TEXT NOT NULL,
  severity              signal_severity NOT NULL DEFAULT 'info',
  title                 TEXT NOT NULL,
  summary               TEXT,
  why_it_matters        TEXT,
  source_name           TEXT NOT NULL,
  source_url            TEXT,
  trust_tier            trust_tier NOT NULL,
  occurred_at           TIMESTAMPTZ NOT NULL,
  ingested_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  geom                  GEOGRAPHY(POINT, 4326),
  related_operator_id   TEXT REFERENCES operator(id),
  related_organization_id TEXT REFERENCES organization(id),
  related_person_ids    TEXT[] NOT NULL DEFAULT '{}',
  source_event_ids      TEXT[] NOT NULL DEFAULT '{}',
  raw_payload_id        TEXT REFERENCES raw_payload(id),
  ai_generated_fields   TEXT[] NOT NULL DEFAULT '{}',
  prompt_version        TEXT,
  source_refs           JSONB NOT NULL,
  confidence_score      REAL NOT NULL DEFAULT 0.5
);

CREATE TABLE trend (
  term              TEXT NOT NULL,
  city              TEXT NOT NULL,
  geography_code    TEXT,
  growth_class      TEXT,
  series            JSONB NOT NULL DEFAULT '[]'::jsonb,
  source_name       TEXT NOT NULL,
  fetched_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  source_refs       JSONB NOT NULL,
  PRIMARY KEY (term, city)
);

CREATE TABLE event (
  id                TEXT PRIMARY KEY,
  title             TEXT NOT NULL,
  host_org_id       TEXT REFERENCES organization(id),
  venue             TEXT,
  geom              GEOGRAPHY(POINT, 4326),
  start_at          TIMESTAMPTZ,
  end_at            TIMESTAMPTZ,
  topics            TEXT[] NOT NULL DEFAULT '{}',
  source            TEXT,
  url               TEXT,
  source_refs       JSONB NOT NULL
);

CREATE TABLE job_posting (
  id                TEXT PRIMARY KEY,
  organization_id   TEXT REFERENCES organization(id),
  operator_id       TEXT REFERENCES operator(id),
  title             TEXT NOT NULL,
  location          TEXT,
  posted_at         TIMESTAMPTZ,
  source            TEXT NOT NULL,
  url               TEXT,
  job_category      TEXT,
  salary_band       TEXT,
  signal_strength   REAL
);

CREATE TABLE trial (
  id                TEXT PRIMARY KEY,
  nct_id            TEXT UNIQUE,
  title             TEXT NOT NULL,
  status            TEXT,
  conditions        TEXT[] NOT NULL DEFAULT '{}',
  sites             JSONB NOT NULL DEFAULT '[]'::jsonb,
  investigators     JSONB NOT NULL DEFAULT '[]'::jsonb,
  sponsor           TEXT,
  last_update       TIMESTAMPTZ,
  source_refs       JSONB NOT NULL
);

CREATE TABLE real_estate_listing (
  id                TEXT PRIMARY KEY,
  kind              TEXT,
  geom              GEOGRAPHY(POINT, 4326),
  submarket         TEXT,
  size_sqft         INT,
  lease_rate        NUMERIC,
  url               TEXT,
  source            TEXT,
  seen_at           TIMESTAMPTZ,
  source_refs       JSONB NOT NULL
);

CREATE INDEX operator_geom_idx ON operator USING GIST (geom);
CREATE INDEX signal_geom_idx ON signal USING GIST (geom);
CREATE INDEX source_event_geom_idx ON source_event USING GIST (geom);
CREATE INDEX signal_occurred_idx ON signal (occurred_at DESC);
CREATE INDEX source_event_occurred_idx ON source_event (occurred_at DESC);
CREATE INDEX operator_name_trgm_idx ON operator USING GIN (normalized_name gin_trgm_ops);
CREATE INDEX organization_name_trgm_idx ON organization USING GIN (normalized_name gin_trgm_ops);
CREATE INDEX person_name_trgm_idx ON person USING GIN (normalized_name gin_trgm_ops);
```

---

## 4. Category Taxonomy

Agents must not invent categories.

Initial enum:

```text
recovery_contrast_therapy
fitness_movement
mind_meditation
spa_thermal
nutrition_longevity
allied_health
womens_health
preventive_diagnostic
mental_health
community_social_wellness
wellness_retail_product
```

### Category Rules

- A record can have multiple categories.
- Store original source categories in payload/provenance.
- Normalize category using deterministic rules first.
- AI can suggest category tags only after deterministic category is stored.
- Analytics cannot ship until category enum and NAICS crosswalk are frozen.

---

## 5. BC Geo-Filter Package

### 5.1 Purpose

Prevent Vancouver, Washington contamination and inconsistent Metro Vancouver scoping.

### 5.2 Required Checks

Order matters:

1. **Coordinate sanity check**
   - latitude: `49.00 <= lat <= 49.40`
   - longitude: `-123.30 <= lng <= -122.50`

2. **PostGIS point-in-polygon**
   - Validate against Metro Vancouver / BC boundary.
   - Boundary source: BC Data Catalogue or official municipal/regional boundary dataset.

3. **Structured address / province check**
   - Accept `BC` or `British Columbia`.
   - Reject `WA`, `Washington`, `Clark County`.

4. **Text-source check**
   - Required positive tokens for non-geocoded text records:
     - `BC`
     - `British Columbia`
     - `Metro Vancouver`
     - `Lower Mainland`
     - named municipality such as Vancouver, Burnaby, Richmond, Surrey, North Vancouver, West Vancouver, Coquitlam, Port Coquitlam, New Westminster, Delta, Langley, Maple Ridge, White Rock, Port Moody.

5. **Negative filters**
   - `Vancouver, WA`
   - `Vancouver WA`
   - `Washington`
   - `Clark County`
   - ZIP prefixes/ranges: `98660` to `98686`

6. **StatCan codes**
   - Vancouver CMA: `933`
   - BC province: `59`

### 5.3 Interface

```python
@dataclass
class CanonicalGeoRecord:
    source_name: str
    title: str | None
    address: str | None
    municipality: str | None
    province: str | None
    country: str | None
    lat: float | None
    lng: float | None
    text: str | None
    statcan_geo_code: str | None
    raw: dict

@dataclass
class GeoGateResult:
    passes: bool
    reason: str | None
    confidence: float

def bc_gate(record: CanonicalGeoRecord, db_session: Session | None = None) -> GeoGateResult:
    ...
```

### 5.4 Test Fixtures

Must include:

Accepted:

- Vancouver, BC
- Burnaby, BC
- Richmond, BC
- Surrey, BC
- Coquitlam, BC
- North Vancouver, BC
- Port Moody, BC
- New Westminster, BC
- White Rock, BC
- Vancouver CMA 933
- BC province 59

Rejected:

- Vancouver, WA
- Vancouver Washington
- Clark County
- ZIP 98660
- ZIP 98661
- ZIP 98662
- ZIP 98663
- ZIP 98664
- ZIP 98665
- ZIP 98682
- ZIP 98683
- ZIP 98684
- ZIP 98685
- ZIP 98686

### 5.5 Acceptance Criteria

- No adapter can persist a geo-aware record without a `bc_gate` result.
- Every rejection writes to `rejected_record`.
- Rejected record includes source name, reason, raw payload pointer, and timestamp.
- Tests pass before any adapter ticket can merge.

---

## 6. Source Adapter Framework

### 6.1 Adapter Contract

```python
from typing import Protocol

class SourceAdapter(Protocol):
    name: str
    family: str
    cadence: str
    trust_tier: str

    def fetch(self) -> list[dict]:
        ...

    def normalize(self, raw: dict) -> list[dict]:
        ...

    def source_record_id(self, raw: dict) -> str:
        ...
```

### 6.2 Runner Flow

```text
for adapter in enabled_adapters:
  create source_run
  fetch raw records
  write raw_payload rows
  normalize into canonical records
  for each canonical record:
    if source is geo-aware:
      run bc_gate
      if rejected:
        write rejected_record
        continue
    upsert canonical entity/event
    write source_event
  generate deterministic signals
  optionally run AI enrichment
  complete source_run
```

### 6.3 Adapter Definition of Done

An adapter is not done unless:

- Source rights row exists in `source_registry`.
- It fetches real named records.
- It stores raw payloads.
- It normalizes into canonical objects.
- It calls `bc_gate` when geo-aware.
- Rejections are logged.
- Upserts are idempotent.
- Deduplication is tested.
- Source provenance is populated.
- `source_run` metrics are visible.
- At least one integration test uses a recorded fixture.

---

## 7. Source Registry

### 7.1 MVP Sources

| Source | Phase | Family | Use | Cadence | Notes |
|---|---:|---|---|---|---|
| City of Vancouver business licences | 0 | directory/regulatory | Operator map spine | Daily | First vertical slice |
| BC Data Catalogue | 0 | geography/data | Boundaries, source discovery | Varies | Polygon source |
| OrgBook BC | 1 | organization | Registration validation | Daily/weekly | BC-only entity spine |
| OSM Overpass | 1 | directory | POI enrichment | Weekly | Respect rate limits, cache |
| Local RSS | 1 | feed | News and openings | Hourly/daily | BC-local outlets |
| BC Gov News RSS | 1 | regulatory/feed | Official changes | Hourly/daily | Official trust tier |
| Health Canada recalls | 1 | recall/feed | Safety/regulatory signals | As published | Official trust tier |
| VCH / Fraser Health pages | 1 | regulatory/context | Inspection/outbreak/context | Weekly/daily | Source-specific scrapes |
| HealthLink BC locator | 1 | directory/context | Service locations | Weekly/manual | Validate access pattern |
| ClinicalTrials.gov | 1/2 | trial/people | Research signals | Weekdays | BC sites only |
| WorkBC / Job Bank | 1 | jobs | Expansion proxy | Daily | BC-filtered |
| GDELT 2.0 DOC | 1/2 | feed | Broad media signals | 15 min/daily | Corroborate before high severity |

### 7.2 Deferred / Paid Sources

| Source | Phase | Use | Gate |
|---|---:|---|---|
| Google Places | 1/2 | Geocoding/enrichment | Add if un-geocoded operator rate >20% |
| Yelp Fusion | 2 | Review/category enrichment | Add only after rights review |
| Google Trends / pytrends | 2 | Peer-city trend tiles | Respect ToS |
| Eventbrite | 2/3 | Events by known orgs | Do not depend on public event search |
| Meetup | 2/3 | Events/community | OAuth approval |
| ORCID/OpenAlex/Crossref | 2/3 | People graph enrichment | Public metadata only |
| Crunchbase/PitchBook | 3 | Funding | Paid use case only |
| Spacelist/BrightCat/CompStak | 3 | CRE | Paid use case only |
| X/Reddit/Meta | 3+ | Social signals | Legal/platform review |
| Mobility/footfall vendors | 3+ | Site selection | Privacy impact assessment |

---

## 8. FastAPI Read API

### 8.1 Public/Internal API Endpoints

```text
GET /health
GET /operators
GET /operators/{id}
GET /signals
GET /signals/{id}
GET /people
GET /people/{id}
GET /entities/{entity_type}/{id}
GET /analytics/whitespace
GET /analytics/category-velocity
GET /trends
GET /admin/source-runs
GET /admin/rejected-records
GET /admin/source-registry
POST /admin/adapters/{source_name}/run
POST /subscriptions      # later
```

### 8.2 Example: Operators

```http
GET /operators?bbox=-123.3,49.0,-122.5,49.4&category=recovery_contrast_therapy&status=open
```

Response:

```json
{
  "items": [
    {
      "id": "op_aetherhaus_vancouver",
      "name": "AetherHaus",
      "categories": ["recovery_contrast_therapy", "community_social_wellness"],
      "status": "open",
      "address": "Vancouver, BC",
      "municipality": "Vancouver",
      "neighborhood": null,
      "lat": 49.2827,
      "lng": -123.1207,
      "confidence_score": 0.82,
      "source_refs": [
        {
          "source_name": "manual_seed",
          "url": "https://example.com",
          "trust_tier": "reputable_press",
          "seen_at": "2026-06-17T00:00:00Z"
        }
      ]
    }
  ],
  "meta": {
    "count": 1,
    "bbox": [-123.3, 49.0, -122.5, 49.4]
  }
}
```

### 8.3 Example: Signals

```http
GET /signals?type=opening&since=2026-01-01T00:00:00Z&severity=notable
```

Response:

```json
{
  "items": [
    {
      "id": "sig_opening_aetherhaus_2026_01",
      "type": "opening",
      "severity": "notable",
      "title": "New recovery club signal: AetherHaus",
      "summary": "A new contrast-therapy/social-wellness operator was detected in Vancouver.",
      "why_it_matters": "Adds evidence that Metro Vancouver's sauna and cold-plunge category is entering a land-grab phase.",
      "source_name": "manual_seed",
      "source_url": "https://example.com",
      "trust_tier": "reputable_press",
      "occurred_at": "2026-01-01T00:00:00Z",
      "lat": 49.2827,
      "lng": -123.1207,
      "related_operator_id": "op_aetherhaus_vancouver",
      "confidence_score": 0.8
    }
  ]
}
```

---

## 9. Frontend Specification

### 9.1 Layout

```text
Top bar:
  - Global search
  - Date range
  - Geography selector
  - Category selector
  - Source trust filter
  - Saved view menu

Left rail:
  - Category filters
  - Recovery-club scorecard
  - Peer-city trend tiles
  - Opportunity shortlist
  - People view toggle

Center:
  - MapLibre map
  - Clustered markers
  - Category color legend
  - White-space heatmap toggle
  - Neighborhood choropleth toggle
  - Draw/select area later

Right rail:
  - Reverse chronological signal feed
  - Signal type filters
  - Severity filters
  - Source freshness indicator
  - Card source/provenance badges

Drawer/overlay:
  - Entity profile
  - Timeline
  - Licence/inspection history
  - Nearby competitors
  - Related people/orgs
  - Source provenance
```

### 9.2 Map Requirements

- Dark visual theme.
- Initial bounds: Metro Vancouver.
- Cluster at low zoom.
- Individual category markers at high zoom.
- Marker color by primary category.
- Marker shape/icon by operator/signal type if possible.
- Click pin opens entity drawer.
- Feed card click flies map to location.
- Feed filters when pin selected.
- Map must never render records outside BC polygon.

### 9.3 Feed Card Requirements

Each card shows:

- signal type
- severity
- title
- summary
- why it matters
- source name
- trust badge
- timestamp
- freshness/cadence
- confidence score
- related entity link
- source URL

### 9.4 Entity Drawer Requirements

Sections:

1. Overview
2. Categories and status
3. Map location
4. Latest signals
5. Source timeline
6. Nearby competitors
7. Related people/organizations
8. Provenance list
9. Confidence notes

### 9.5 Mobile

- Map remains first.
- Feed becomes bottom sheet.
- Filters become horizontal chips.
- Drawer becomes full-screen sheet.
- Source badge and freshness remain visible.

---

## 10. AI Signal Pipeline

### 10.1 Principle

AI enriches existing source-backed records. It does not create facts from nothing.

### 10.2 Deterministic First

Generate source events and baseline signals without AI for:

- new licence
- licence change
- possible closure
- new inspection/closure page
- official outbreak/public-health signal
- recall
- job posting
- event posting
- trial update
- source news item

### 10.3 AI Enrichment Fields

AI may populate:

- `summary`
- `why_it_matters`
- category suggestions
- entity extraction candidates
- severity suggestion
- dedupe suggestion

AI output must store:

- prompt version
- model name
- input source event IDs
- generated fields list
- confidence
- raw model output

### 10.4 AI Guardrails

- Do not invent facts.
- Do not summarize beyond source evidence.
- Do not infer patient data or private personal attributes.
- Do not rank ordinary individuals from private data.
- Mark uncertain matches as low confidence.
- Human review required for high-severity public-facing signals until confidence rules are proven.

### 10.5 AI Prompt Template

```text
You are enriching a public market-intelligence signal for the Metro Vancouver wellness sector.

Use only the supplied source event and source text.
Do not invent facts.
Do not include medical advice.
Do not infer private personal information.
Return strict JSON.

Input:
{source_event_json}

Return:
{
  "title": "...",
  "summary": "...",
  "why_it_matters": "...",
  "signal_type": "...",
  "category_tags": ["..."],
  "related_operator_candidates": [{"name": "...", "confidence": 0.0}],
  "related_person_candidates": [{"name": "...", "confidence": 0.0}],
  "severity": "info|notable|high",
  "confidence_score": 0.0,
  "needs_review": true
}
```

---

## 11. People and Influence Graph

### 11.1 People Classes

- founders/operators
- investors
- practitioners
- researchers/academics
- policy/public-health figures
- creators/community organizers
- event hosts

### 11.2 Allowed Data

Allowed:

- public websites
- public event pages
- public company pages
- public ORCID/OpenAlex/Crossref metadata
- public news mentions
- public government/health authority pages
- manually entered source-backed facts

Not allowed:

- private social data
- patient data
- inferred diagnoses
- private contact details
- scraped LinkedIn content
- sensitive personal attributes

### 11.3 Influence Score

```text
Influence Score =
0.25 * institutional_authority
+ 0.20 * network_centrality
+ 0.15 * research_or_clinical_leadership
+ 0.15 * media_velocity
+ 0.10 * capital_power
+ 0.10 * event_convening
+ 0.05 * public_reach
```

Apply:

- locality multiplier
- recency decay
- confidence score

### 11.4 UI Requirements

- Leaderboard.
- Component breakdown.
- Confidence badge.
- Explanation: “Why this person appears.”
- Correction/request update path before public launch.
- Sigma.js graph view with graphology:
  - nodes: people/orgs/operators/events
  - edges: founder, employee, advisor, investor, speaker, co-author, mentioned-with
  - centrality metrics
  - Louvain communities
  - ForceAtlas2 layout in worker

---

## 12. Opportunity Scoring

### 12.1 Initial Formula

```text
Opportunity Score =
0.30 demand_proxy
+ 0.20 low_supply_density
+ 0.15 category_growth
+ 0.15 target_demo_fit
+ 0.10 transit_access
+ 0.05 event_community_activity
+ 0.05 source_confidence
```

### 12.2 Required Inputs

- operator density by category
- new operators in 30/90/180 days
- job velocity
- event velocity
- news/signal velocity
- population/demographic denominators
- business counts / NAICS
- neighborhood/municipality polygon
- later: CRE availability and lease rate

### 12.3 Analytics Rules

- No score without source confidence.
- Every score component must be inspectable.
- Heatmaps must expose calculation method.
- Do not claim economic attractiveness without caveat.
- White-space means “supply-demand signal,” not guaranteed success.

---

## 13. GitHub / Agent Workflow

### 13.1 Branch Rules

- `main` protected.
- All changes via PR.
- Required checks:
  - web lint/typecheck
  - Python lint/typecheck
  - unit tests
  - migration check
  - geo-filter tests
  - adapter fixture tests
- CODEOWNERS required for:
  - `packages/geo/**`
  - `db/migrations/**`
  - `apps/jobs/adapters/**`
  - `.github/workflows/**`
  - `CLAUDE.md`

### 13.2 Agent Permissions

- Agent may open branches and PRs.
- Agent may not push directly to `main`.
- Agent may not alter secrets or deployment credentials.
- Agent may not relax CI.
- Agent may not disable geo-filter tests.
- Agent may not remove provenance requirements.
- Agent may not add new data source without source rights row.

### 13.3 Claude/GitHub Action

Use a GitHub Action only after repo bootstrapping. Recommended modes:

- PR review only at first.
- Issue-comment trigger later.
- Minimum permissions.
- No automatic deployment from agent-authored PRs without human approval.
- Treat external issue/PR text as untrusted input.

---

## 14. CI/CD

### 14.1 CI Workflow

```yaml
name: ci

on:
  pull_request:
  push:
    branches: [main]

jobs:
  web:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - run: pnpm install --frozen-lockfile
      - run: pnpm lint
      - run: pnpm typecheck
      - run: pnpm test

  python:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgis/postgis:16-3.4
        env:
          POSTGRES_PASSWORD: postgres
        ports: ["5432:5432"]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - run: uv run ruff check .
      - run: uv run mypy apps packages
      - run: uv run pytest
      - run: uv run alembic upgrade head
```

### 14.2 Deployment Environments

| Environment | Purpose |
|---|---|
| local | Docker Compose |
| dev | Shared agent/dev testing |
| staging | Pre-prod with scheduled jobs |
| production | Operator-facing system |

### 14.3 Secrets

```text
DATABASE_URL
REDIS_URL
RAW_STORAGE_BUCKET
RAW_STORAGE_ACCESS_KEY
RAW_STORAGE_SECRET_KEY
ANTHROPIC_API_KEY
GOOGLE_PLACES_API_KEY
YELP_API_KEY
MAPTILER_API_KEY
SENTRY_DSN
```

---

## 15. Observability

### 15.1 Metrics

- API latency
- API error rate
- map query latency
- adapter run success/failure
- records fetched/persisted/rejected
- source freshness age
- AI enrichment cost
- AI enrichment error rate
- rejected WA contamination count
- geocoding hit rate
- fuzzy match confidence distribution

### 15.2 Logs

Structured JSON logs with:

- request ID
- source name
- adapter run ID
- entity ID
- source event ID
- signal ID
- reject reason
- prompt version where relevant

### 15.3 Alerts

- source stale beyond SLA
- adapter failed twice consecutively
- rejected-record spike
- API health failure
- no signals generated in expected window
- database migration failure
- AI cost threshold exceeded

---

## 16. Security and Governance

### 16.1 Required Governance

- Source-rights matrix before adapter merge.
- Data field allowlists per source.
- Provenance visible on every card/pin/score.
- Freshness visible on every card/pin/score.
- No patient-level data.
- No small-count health data.
- No private mobility traces.
- No LinkedIn scraping.
- Raw social data deferred.
- High-severity public signals require review until confidence is proven.

### 16.2 Data Retention

- Raw payload retention: 90 days in MVP unless licensing requires shorter.
- Derived canonical records retained indefinitely with provenance.
- Rejected records retained for audit.
- Source deletions respected where terms require.

### 16.3 Licence Attribution

UI footer and source drawer must include open-government attribution where required.

---

## 17. Milestones

### Milestone 0 — Repo Harness

Exit:

- Docker Compose starts web/API/PostGIS.
- Migrations apply.
- `CLAUDE.md` committed.
- CI green.
- Seed data renders in UI.

### Milestone 1 — BC-Only Vertical Slice

Exit:

- BC geo-filter package complete.
- City of Vancouver licences adapter ingests real records.
- API returns real operators.
- Map renders real operators.
- Entity drawer shows source provenance.
- WA contamination tests pass.

### Milestone 2 — MVP Private Alpha

Exit:

- OSM Overpass, OrgBook, RSS, and at least one official regulatory/feed adapter.
- Signal feed live.
- Map/feed sync works.
- Manual people seed import.
- Leaderboard stub.
- AI `why_it_matters` enrichment.
- Source freshness admin page.

### Milestone 3 — Intelligence Beta

Exit:

- Entity resolution.
- Opportunity heatmap.
- Category velocity analytics.
- Peer-city trend tiles.
- Sigma.js graph.
- Influence score explainability.

### Milestone 4 — Production Hardening

Exit:

- RBAC.
- Audit logs.
- Alert subscriptions.
- Export/snapshots.
- Kiosk mode.
- Deployment runbooks.
- Monitoring/alerts.

---

## 18. Issue Backlog

Use the provided `github_issues.csv` for issue import. Labels:

```text
epic:foundation
epic:ingestion
epic:frontend
epic:geo
epic:ai
epic:analytics
epic:people
epic:governance
epic:ops
priority:p0
priority:p1
priority:p2
blocked
agent-ready
needs-human-review
```

Definition of done for every issue:

- Tests added/updated.
- Docs updated where relevant.
- Acceptance criteria satisfied.
- No placeholder data unless the issue explicitly says seed/stub.
- Source provenance intact.
- CI green.

---

## 19. First 10 Agent Moves

1. Create repo scaffold.
2. Add Docker Compose with PostGIS.
3. Add database migrations.
4. Add `CLAUDE.md`.
5. Build BC geo-filter package and tests.
6. Build adapter runner.
7. Seed `source_registry`.
8. Build City Vancouver licence adapter.
9. Expose `/operators` and `/signals`.
10. Render MapLibre map + feed + entity drawer.

---

## 20. Agent Prompts

### Backend/Data Agent

```text
You are implementing the backend/data layer for P-U-C/wellness-radar.

Build a composable ingestion system where each adapter fetches raw records, stores raw payloads, normalizes into canonical objects, passes geo-aware records through the mandatory BC geo-filter, persists into Postgres/PostGIS, and emits source_events/signals with full provenance.

Start with:
1. Database migrations.
2. Source registry seed.
3. BC geo-filter integration.
4. SourceAdapter interface.
5. City of Vancouver business licences adapter.
6. GET /operators, GET /signals, GET /entities/{entity_type}/{id}, GET /admin/source-runs.

Constraints:
- No geo-aware record persists without bc_gate approval.
- No record displays without source_refs.
- Official-source signals must work without AI.
- AI can enrich only after deterministic source_event creation.
- No placeholders count as done.
```

### Frontend Agent

```text
You are implementing the frontend for P-U-C/wellness-radar.

Build a dark, map-first intelligence dashboard with MapLibre GL, synchronized signal feed, filters, entity drawer, source provenance, and responsive mobile bottom-sheet layout.

Critical interactions:
- Click map pin -> open entity drawer and filter/highlight feed.
- Click feed card -> fly map to related location and open entity drawer.
- Category/date/source filters update map and feed together.
- Every pin/card/score shows source, timestamp, confidence, and provenance link.
- Map must never render records outside BC bounds.
```

### AI/Signal Agent

```text
You are implementing the AI signal enrichment layer for P-U-C/wellness-radar.

Transform deterministic source_events into concise intelligence cards.

Rules:
- Use only supplied source payloads.
- Do not invent facts.
- Do not produce medical advice.
- Do not infer private personal information.
- Return strict JSON.
- Mark uncertain entity matches low confidence.
- Store prompt_version, model name, and generated field list.
- Every generated signal links to source_refs.
```

### Analytics Agent

```text
You are implementing opportunity analytics for P-U-C/wellness-radar.

Build category velocity, supply density, and white-space scoring using PostGIS and normalized operators/signals.

Rules:
- No score without component breakdown.
- No score without source confidence.
- Do not claim guaranteed economic attractiveness.
- Make every heatmap cell traceable to source data.
- Start with recovery_contrast_therapy.
```

---

## 21. Acceptance Gates

### Phase 0 Gate

- Real City licence records visible on map.
- No WA fixtures pass.
- Source provenance visible.
- CI green.

### MVP Gate

- User can answer:
  - What recovery/wellness operators exist?
  - What changed this week?
  - Who should I watch?
  - Which neighborhoods/categories have momentum?

### Production Gate

- Freshness monitor live.
- Adapter failure alerts live.
- RBAC in place.
- Source-rights registry complete.
- Public people scoring has correction workflow.
- Export/snapshot working.
