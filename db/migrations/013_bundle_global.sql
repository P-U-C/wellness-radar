INSERT INTO source_registry (
  source_name, family, base_url, cadence, licence, cost, trust_tier, geo_rule, phase, rights_notes, enabled
) VALUES
  (
    'osm_overpass_first_mover',
    'reference_city_supply',
    'https://overpass-api.de/',
    'weekly/cache_first',
    'Open Database License',
    'free',
    'community',
    'Reference city aggregate POI counts only. Do not persist non-BC POIs to operator/source_event tables and do not run bc_gate; rows are bundle-level benchmark signal with Overpass query provenance.',
    3,
    'OpenStreetMap data via Overpass API, licensed under ODbL. R3 stores aggregate city counts and the query/raw response only; attribution and ODbL notice must be displayed wherever these benchmark counts are shown.',
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
SET
  family = 'global_news_timeline',
  base_url = 'https://api.gdeltproject.org/api/v2/doc/doc',
  cadence = 'daily/cache_first',
  licence = 'GDELT Project terms',
  cost = 'free',
  trust_tier = 'community',
  geo_rule = 'Global aggregate news attention only; no BC geo gate because no geo-aware records are persisted.',
  phase = 3,
  rights_notes = 'GDELT 2.0 DOC API timelinevol aggregate news attention. R3 stores aggregate timeline volume responses, query URLs, and source metadata only; no full article text is republished. Display should attribute GDELT and source status.',
  enabled = TRUE,
  updated_at = now()
WHERE source_name = 'gdelt_doc';

CREATE TABLE IF NOT EXISTS bundle_global (
  bundle_id          TEXT PRIMARY KEY REFERENCES bundle(id) ON DELETE CASCADE,
  worldwide_match    JSONB NOT NULL,
  source_refs        JSONB NOT NULL,
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (jsonb_typeof(worldwide_match) = 'object'),
  CHECK (worldwide_match ? 'direction'),
  CHECK (worldwide_match ? 'value'),
  CHECK (worldwide_match ? 'verdict'),
  CHECK (worldwide_match ? 'source_status'),
  CHECK ((worldwide_match->>'source_status') IN ('live', 'cached', 'fixture_fallback')),
  CHECK (jsonb_typeof(source_refs) = 'array'),
  CHECK (jsonb_array_length(source_refs) > 0)
);

CREATE TABLE IF NOT EXISTS bundle_first_mover_city (
  bundle_id            TEXT NOT NULL REFERENCES bundle(id) ON DELETE CASCADE,
  city                 TEXT NOT NULL,
  count                INT NOT NULL CHECK (count >= 0),
  density              REAL NOT NULL CHECK (density >= 0),
  ratio_vs_vancouver   REAL NOT NULL CHECK (ratio_vs_vancouver >= 0),
  source_status        TEXT NOT NULL CHECK (source_status IN ('live', 'cached', 'fixture_fallback')),
  source_refs          JSONB NOT NULL,
  confidence_score     REAL NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
  source_error         TEXT,
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (bundle_id, city),
  CHECK (jsonb_typeof(source_refs) = 'array'),
  CHECK (jsonb_array_length(source_refs) > 0)
);

CREATE INDEX IF NOT EXISTS bundle_first_mover_city_rank_idx
  ON bundle_first_mover_city (bundle_id, ratio_vs_vancouver DESC, city);
