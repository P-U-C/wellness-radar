INSERT INTO source_registry (
  source_name, family, base_url, cadence, licence, cost, trust_tier, geo_rule, phase, rights_notes, enabled
) VALUES
  (
    'city_vancouver_local_area_boundary',
    'boundary/open_data',
    'https://opendata.vancouver.ca/explore/dataset/local-area-boundary/',
    'rarely_changes',
    'Open Government Licence - Vancouver',
    'free',
    'official',
    'Boundary polygons and centroids are City of Vancouver, BC local areas; centroid records must pass bc_gate before persistence.',
    5,
    'City of Vancouver Open Data Portal dataset "Local area boundary"; licensed under the Open Government Licence - Vancouver. Use with attribution; local-area boundaries follow approximate street centrelines per dataset notes.',
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
  base_url = 'https://www.statcan.gc.ca/en/developers/wds',
  licence = 'Statistics Canada Open Licence',
  rights_notes = 'Statistics Canada WDS and 2021 Census Profile official aggregate data. CM5 uses live Census Profile population and Table 33-10-1016-01 Canadian Business Counts with employees; cache retained only to avoid re-downloading unchanged official outputs. Attribution required under Statistics Canada terms.',
  updated_at = now()
WHERE source_name = 'statcan_wds';

CREATE TABLE IF NOT EXISTS neighborhood_boundary (
  id                 TEXT PRIMARY KEY,
  source_name        TEXT NOT NULL REFERENCES source_registry(source_name),
  municipality       TEXT NOT NULL,
  neighborhood       TEXT NOT NULL,
  geom               GEOGRAPHY(MULTIPOLYGON, 4326) NOT NULL,
  centroid           GEOGRAPHY(POINT, 4326) NOT NULL,
  source_refs        JSONB NOT NULL,
  confidence_score   REAL NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
  bc_gate_result     JSONB NOT NULL DEFAULT '{}'::jsonb,
  payload            JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (jsonb_typeof(source_refs) = 'array'),
  CHECK (jsonb_array_length(source_refs) > 0),
  UNIQUE (source_name, municipality, neighborhood)
);

CREATE INDEX IF NOT EXISTS neighborhood_boundary_geom_idx
  ON neighborhood_boundary USING GIST (geom);

CREATE INDEX IF NOT EXISTS neighborhood_boundary_centroid_idx
  ON neighborhood_boundary USING GIST (centroid);

ALTER TABLE "operator"
  ADD COLUMN IF NOT EXISTS neighborhood_assignment_method TEXT,
  ADD COLUMN IF NOT EXISTS neighborhood_assignment_source TEXT,
  ADD COLUMN IF NOT EXISTS neighborhood_assignment_confidence REAL
    CHECK (
      neighborhood_assignment_confidence IS NULL
      OR (
        neighborhood_assignment_confidence >= 0
        AND neighborhood_assignment_confidence <= 1
      )
    ),
  ADD COLUMN IF NOT EXISTS neighborhood_assignment_updated_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS operator_neighborhood_idx
  ON "operator" (municipality, neighborhood);
