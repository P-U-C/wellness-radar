CREATE TABLE IF NOT EXISTS daily_brief (
  id                 TEXT PRIMARY KEY,
  brief_date         DATE NOT NULL UNIQUE,
  generated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  window_start       TIMESTAMPTZ NOT NULL,
  window_end         TIMESTAMPTZ NOT NULL,
  status             TEXT NOT NULL CHECK (
    status IN ('material_changes', 'no_material_changes', 'initial_snapshot')
  ),
  brief_text         TEXT NOT NULL,
  sections           JSONB NOT NULL DEFAULT '{}'::jsonb,
  top_actions        JSONB NOT NULL DEFAULT '[]'::jsonb,
  counts             JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_refs        JSONB NOT NULL DEFAULT '[]'::jsonb,
  narrative_model    TEXT NOT NULL DEFAULT 'deterministic-template-v1',
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (window_end >= window_start),
  CHECK (jsonb_typeof(sections) = 'object'),
  CHECK (jsonb_typeof(top_actions) = 'array'),
  CHECK (jsonb_typeof(counts) = 'object'),
  CHECK (jsonb_typeof(source_refs) = 'array')
);

CREATE INDEX IF NOT EXISTS daily_brief_generated_at_idx
  ON daily_brief (generated_at DESC);

CREATE TABLE IF NOT EXISTS opportunity_score_snapshot (
  id                  TEXT PRIMARY KEY,
  brief_date          DATE NOT NULL,
  scorecard_id        TEXT NOT NULL,
  category            TEXT NOT NULL,
  geo_code            TEXT NOT NULL,
  geo_name            TEXT NOT NULL,
  opportunity_score   REAL NOT NULL,
  source_refs         JSONB NOT NULL,
  confidence_score    REAL NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
  calculation_method  TEXT NOT NULL,
  captured_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (brief_date, scorecard_id),
  CHECK (jsonb_typeof(source_refs) = 'array'),
  CHECK (jsonb_array_length(source_refs) > 0)
);

CREATE INDEX IF NOT EXISTS opportunity_score_snapshot_scorecard_idx
  ON opportunity_score_snapshot (scorecard_id, captured_at DESC);

ALTER TABLE alert_subscription
  DROP CONSTRAINT IF EXISTS alert_subscription_conditions_check;

ALTER TABLE alert_subscription
  ADD CONSTRAINT alert_subscription_conditions_check
  CHECK (
    conditions <@ ARRAY[
      'source_stale_beyond_sla',
      'adapter_run_failed',
      'adapter_failed_twice',
      'rejected_record_spike',
      'api_health_failure',
      'no_signals_window',
      'migration_failure',
      'ai_cost_threshold',
      'daily_market_brief'
    ]::text[]
  );
