ALTER TABLE organization
  ADD COLUMN IF NOT EXISTS orgbook_match_status TEXT NOT NULL DEFAULT 'unmatched',
  ADD COLUMN IF NOT EXISTS orgbook_match_confidence REAL NOT NULL DEFAULT 0.0;

ALTER TABLE signal
  ADD COLUMN IF NOT EXISTS ai_model TEXT,
  ADD COLUMN IF NOT EXISTS ai_category_suggestions TEXT[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS ai_severity_suggestion signal_severity,
  ADD COLUMN IF NOT EXISTS ai_confidence_score REAL;

INSERT INTO source_registry (
  source_name, family, base_url, cadence, licence, cost, trust_tier, geo_rule, phase, rights_notes, enabled
) VALUES
  (
    'manual_seed',
    'directory/seed',
    NULL,
    'manual',
    'source-specific public pages',
    'free',
    'informal',
    'Metro Vancouver coordinates and BC address text must pass bc_gate before persist.',
    1,
    'needs_review: manual seed uses public operator pages or public directory pages; verify attribution before production.',
    TRUE
  ),
  (
    'manual_people_csv',
    'people/seed',
    NULL,
    'manual',
    'source-specific public professional pages',
    'free',
    'informal',
    'Public professional data only; no private/social/LinkedIn/patient data.',
    1,
    'needs_review: manually curated public professional records only; review each source before production.',
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

UPDATE source_registry
SET enabled = TRUE,
    updated_at = now()
WHERE source_name IN (
  'orgbook_bc',
  'osm_overpass',
  'local_rss',
  'bc_gov_news_rss',
  'health_canada_recalls'
);
