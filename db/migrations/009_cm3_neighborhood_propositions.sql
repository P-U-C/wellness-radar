INSERT INTO source_registry (
  source_name, family, base_url, cadence, licence, cost, trust_tier, geo_rule, phase, rights_notes, enabled
) VALUES
  (
    'derived_neighborhood_analytics',
    'analytics/derived',
    NULL,
    'on_analytics_run',
    'Derived from existing source-backed records; see each record source_refs',
    'free',
    'informal',
    'Derived neighborhood centroids must be computed from BC-gated operators and must pass bc_gate before persistence.',
    3,
    'Internal derived analytics only. No new external data rights are introduced; displayed records must carry source_refs from the underlying operator and StatCan denominator sources.',
    TRUE
  )
ON CONFLICT (source_name) DO UPDATE SET
  family = EXCLUDED.family,
  base_url = EXCLUDED.base_url,
  cadence = EXCLUDED.cadence,
  licence = EXCLUDED.licence,
  cost = EXCLUDED.cost,
  trust_tier = EXCLUDED.trust_tier,
  geo_rule = EXCLUDED.geo_rule,
  phase = EXCLUDED.phase,
  rights_notes = EXCLUDED.rights_notes,
  enabled = EXCLUDED.enabled,
  updated_at = now();

ALTER TABLE opportunity_scorecard
  ADD COLUMN IF NOT EXISTS geo_level TEXT NOT NULL DEFAULT 'CSD';

CREATE INDEX IF NOT EXISTS opportunity_scorecard_geo_level_idx
  ON opportunity_scorecard (geo_level, category, opportunity_score DESC);

ALTER TABLE opportunity_score_snapshot
  ADD COLUMN IF NOT EXISTS geo_level TEXT NOT NULL DEFAULT 'CSD';

CREATE TABLE IF NOT EXISTS opportunity_proposition (
  id                                TEXT PRIMARY KEY,
  heatmap_cell_id                   TEXT NOT NULL REFERENCES opportunity_heatmap_cell(id) ON DELETE CASCADE,
  category                          TEXT NOT NULL REFERENCES category_taxonomy(category),
  geo_code                          TEXT NOT NULL REFERENCES statcan_geography(geo_code),
  geo_name                          TEXT NOT NULL,
  geo_level                         TEXT NOT NULL,
  municipality                      TEXT,
  headline                          TEXT NOT NULL,
  summary                           TEXT NOT NULL,
  competitor_count_within_radius    INT NOT NULL CHECK (competitor_count_within_radius >= 0),
  competitor_radius_km              REAL NOT NULL CHECK (competitor_radius_km > 0),
  population                        NUMERIC,
  business_count                    NUMERIC,
  demand_source                     TEXT NOT NULL,
  supporting_signals                JSONB NOT NULL DEFAULT '[]'::jsonb,
  component_breakdown               JSONB NOT NULL DEFAULT '{}'::jsonb,
  opportunity_score                 REAL NOT NULL,
  confidence_score                  REAL NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
  source_refs                       JSONB NOT NULL,
  generated_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (jsonb_typeof(supporting_signals) = 'array'),
  CHECK (jsonb_typeof(component_breakdown) = 'object'),
  CHECK (jsonb_typeof(source_refs) = 'array'),
  CHECK (jsonb_array_length(source_refs) > 0),
  UNIQUE (category, geo_code)
);

CREATE INDEX IF NOT EXISTS opportunity_proposition_rank_idx
  ON opportunity_proposition (geo_level, category, opportunity_score DESC, confidence_score DESC);
