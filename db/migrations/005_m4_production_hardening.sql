DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'app_role') THEN
    CREATE TYPE app_role AS ENUM ('viewer', 'analyst', 'admin');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS app_user (
  id            TEXT PRIMARY KEY,
  email         TEXT UNIQUE NOT NULL,
  display_name  TEXT NOT NULL,
  role          app_role NOT NULL DEFAULT 'viewer',
  active        BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_log (
  id              BIGSERIAL PRIMARY KEY,
  occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  action          TEXT NOT NULL,
  actor_role      TEXT,
  actor_id        TEXT,
  request_id      TEXT,
  source_name     TEXT,
  source_run_id   BIGINT REFERENCES source_run(id) ON DELETE SET NULL,
  entity_type     TEXT,
  entity_id       TEXT,
  source_event_id TEXT REFERENCES source_event(id) ON DELETE SET NULL,
  signal_id       TEXT REFERENCES signal(id) ON DELETE SET NULL,
  reject_reason   TEXT,
  prompt_version  TEXT,
  metadata        JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS audit_log_occurred_idx ON audit_log (occurred_at DESC);
CREATE INDEX IF NOT EXISTS audit_log_request_id_idx ON audit_log (request_id);
CREATE INDEX IF NOT EXISTS audit_log_source_run_idx ON audit_log (source_run_id);

CREATE TABLE IF NOT EXISTS alert_subscription (
  id              TEXT PRIMARY KEY,
  user_id         TEXT REFERENCES app_user(id) ON DELETE SET NULL,
  owner_email     TEXT NOT NULL,
  name            TEXT NOT NULL,
  categories      TEXT[] NOT NULL DEFAULT '{}',
  geography       JSONB NOT NULL DEFAULT '{}'::jsonb,
  conditions      TEXT[] NOT NULL DEFAULT '{}',
  channel         TEXT NOT NULL DEFAULT 'dispatch_stub',
  target          TEXT,
  enabled         BOOLEAN NOT NULL DEFAULT TRUE,
  created_by_role TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (
    conditions <@ ARRAY[
      'source_stale_beyond_sla',
      'adapter_failed_twice',
      'rejected_record_spike',
      'api_health_failure',
      'no_signals_window',
      'migration_failure',
      'ai_cost_threshold'
    ]::text[]
  )
);

CREATE INDEX IF NOT EXISTS alert_subscription_enabled_idx
  ON alert_subscription (enabled, owner_email);

CREATE TABLE IF NOT EXISTS alert_dispatch (
  id                BIGSERIAL PRIMARY KEY,
  subscription_id   TEXT REFERENCES alert_subscription(id) ON DELETE CASCADE,
  condition         TEXT NOT NULL,
  status            TEXT NOT NULL DEFAULT 'stubbed',
  payload           JSONB NOT NULL DEFAULT '{}'::jsonb,
  dispatched_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS export_snapshot (
  id              TEXT PRIMARY KEY,
  snapshot_type   TEXT NOT NULL CHECK (snapshot_type IN ('operators', 'signals', 'graph')),
  format          TEXT NOT NULL CHECK (format IN ('json', 'csv')),
  status          TEXT NOT NULL DEFAULT 'ready',
  requested_by    TEXT,
  row_count       INT NOT NULL DEFAULT 0,
  storage_uri     TEXT,
  manifest        JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS export_snapshot_created_idx ON export_snapshot (created_at DESC);

CREATE TABLE IF NOT EXISTS people_correction_request (
  id                  TEXT PRIMARY KEY,
  person_id           TEXT NOT NULL REFERENCES person(id) ON DELETE CASCADE,
  requester_name      TEXT,
  requester_email     TEXT,
  correction_summary  TEXT NOT NULL,
  status              TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open', 'reviewing', 'accepted', 'rejected', 'closed')),
  source_refs         JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_by_role     TEXT,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_at         TIMESTAMPTZ,
  reviewed_by         TEXT
);

CREATE INDEX IF NOT EXISTS people_correction_person_idx
  ON people_correction_request (person_id, status);

UPDATE source_registry
SET rights_notes = CASE source_name
  WHEN 'city_vancouver_business_licences'
    THEN 'reviewed: City of Vancouver Open Data Portal terms allow reuse with attribution/source links; retain source_refs and do not imply City endorsement.'
  WHEN 'bc_gov_news_rss'
    THEN 'reviewed: BC Government public news pages may be linked and excerpted conservatively with attribution; retain source_refs and avoid medical/legal claims.'
  WHEN 'health_canada_recalls'
    THEN 'reviewed: Government of Canada recall notices are official public safety records; display source links, attribution, and no clinical advice.'
  WHEN 'bc_data_catalogue'
    THEN 'reviewed: BC Open Government Licence data can be used with attribution; final boundary dataset selection remains a data-quality review item.'
  WHEN 'statcan_wds'
    THEN 'reviewed: Statistics Canada WDS/open-data use requires attribution; M3 fixture table/vector selection remains needs-human-review before public production.'
  ELSE rights_notes
END,
updated_at = now()
WHERE source_name IN (
  'city_vancouver_business_licences',
  'bc_gov_news_rss',
  'health_canada_recalls',
  'bc_data_catalogue',
  'statcan_wds'
);
