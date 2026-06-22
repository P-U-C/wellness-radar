ALTER TABLE opportunity_proposition
  ADD COLUMN IF NOT EXISTS thesis TEXT,
  ADD COLUMN IF NOT EXISTS market_sizing_line TEXT,
  ADD COLUMN IF NOT EXISTS spend_proxy_label TEXT,
  ADD COLUMN IF NOT EXISTS spend_proxy_value NUMERIC,
  ADD COLUMN IF NOT EXISTS nearest_competitors JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS confidence_narrative TEXT;

ALTER TABLE opportunity_proposition
  DROP CONSTRAINT IF EXISTS opportunity_proposition_nearest_competitors_json;

ALTER TABLE opportunity_proposition
  ADD CONSTRAINT opportunity_proposition_nearest_competitors_json
  CHECK (jsonb_typeof(nearest_competitors) = 'array');

CREATE INDEX IF NOT EXISTS opportunity_proposition_category_geo_rank_idx
  ON opportunity_proposition (category, geo_level, opportunity_score DESC, confidence_score DESC);
