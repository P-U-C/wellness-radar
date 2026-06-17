CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'trust_tier') THEN
    CREATE TYPE trust_tier AS ENUM ('official', 'reputable_press', 'commercial_api', 'community', 'informal', 'ai_inferred');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'operator_status') THEN
    CREATE TYPE operator_status AS ENUM ('open', 'new', 'planned', 'closed', 'rumored', 'unknown');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'signal_severity') THEN
    CREATE TYPE signal_severity AS ENUM ('info', 'notable', 'high');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'source_run_status') THEN
    CREATE TYPE source_run_status AS ENUM ('success', 'partial', 'failed');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS source_registry (
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

CREATE TABLE IF NOT EXISTS raw_payload (
  id                TEXT PRIMARY KEY,
  source_name       TEXT NOT NULL REFERENCES source_registry(source_name),
  source_record_id  TEXT,
  fetched_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  content_hash      TEXT NOT NULL,
  storage_uri       TEXT,
  raw_json          JSONB,
  raw_text          TEXT
);

CREATE TABLE IF NOT EXISTS source_run (
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

CREATE TABLE IF NOT EXISTS rejected_record (
  id                BIGSERIAL PRIMARY KEY,
  source_name       TEXT NOT NULL,
  reason            TEXT NOT NULL,
  raw_payload_id    TEXT,
  raw               JSONB,
  rejected_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS organization (
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

CREATE TABLE IF NOT EXISTS "operator" (
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

CREATE TABLE IF NOT EXISTS person (
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

CREATE TABLE IF NOT EXISTS source_event (
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

CREATE TABLE IF NOT EXISTS signal (
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
  related_operator_id   TEXT REFERENCES "operator"(id),
  related_organization_id TEXT REFERENCES organization(id),
  related_person_ids    TEXT[] NOT NULL DEFAULT '{}',
  source_event_ids      TEXT[] NOT NULL DEFAULT '{}',
  raw_payload_id        TEXT REFERENCES raw_payload(id),
  ai_generated_fields   TEXT[] NOT NULL DEFAULT '{}',
  prompt_version        TEXT,
  source_refs           JSONB NOT NULL,
  confidence_score      REAL NOT NULL DEFAULT 0.5
);

CREATE TABLE IF NOT EXISTS trend (
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

CREATE TABLE IF NOT EXISTS event (
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

CREATE TABLE IF NOT EXISTS job_posting (
  id                TEXT PRIMARY KEY,
  organization_id   TEXT REFERENCES organization(id),
  operator_id       TEXT REFERENCES "operator"(id),
  title             TEXT NOT NULL,
  location          TEXT,
  posted_at         TIMESTAMPTZ,
  source            TEXT NOT NULL,
  url               TEXT,
  job_category      TEXT,
  salary_band       TEXT,
  signal_strength   REAL
);

CREATE TABLE IF NOT EXISTS trial (
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

CREATE TABLE IF NOT EXISTS real_estate_listing (
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

CREATE INDEX IF NOT EXISTS operator_geom_idx ON "operator" USING GIST (geom);
CREATE INDEX IF NOT EXISTS signal_geom_idx ON signal USING GIST (geom);
CREATE INDEX IF NOT EXISTS source_event_geom_idx ON source_event USING GIST (geom);
CREATE INDEX IF NOT EXISTS signal_occurred_idx ON signal (occurred_at DESC);
CREATE INDEX IF NOT EXISTS source_event_occurred_idx ON source_event (occurred_at DESC);
CREATE INDEX IF NOT EXISTS operator_name_trgm_idx ON "operator" USING GIN (normalized_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS organization_name_trgm_idx ON organization USING GIN (normalized_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS person_name_trgm_idx ON person USING GIN (normalized_name gin_trgm_ops);
