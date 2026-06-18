DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'entity_match_status') THEN
    CREATE TYPE entity_match_status AS ENUM ('candidate', 'merged', 'rejected', 'reversed');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS category_taxonomy (
  category          TEXT PRIMARY KEY,
  label             TEXT NOT NULL,
  description       TEXT NOT NULL,
  frozen_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  source_refs       JSONB NOT NULL,
  needs_human_review BOOLEAN NOT NULL DEFAULT TRUE,
  active            BOOLEAN NOT NULL DEFAULT TRUE
);

INSERT INTO category_taxonomy (
  category, label, description, source_refs, needs_human_review
) VALUES
  (
    'recovery_contrast_therapy',
    'Recovery and contrast therapy',
    'Sauna, cold plunge, contrast therapy, cryotherapy, recovery clubs, float, and bathhouse concepts.',
    '[{"source_name":"agent_spec","url":"AGENT_SPEC.md#4-category-taxonomy","trust_tier":"official","seen_at":"2026-06-18T00:00:00Z","source_record_id":"s4","licence":null}]'::jsonb,
    TRUE
  ),
  (
    'fitness_movement',
    'Fitness and movement',
    'Fitness, gyms, pilates, yoga, barre, dance, martial arts, and movement training.',
    '[{"source_name":"agent_spec","url":"AGENT_SPEC.md#4-category-taxonomy","trust_tier":"official","seen_at":"2026-06-18T00:00:00Z","source_record_id":"s4","licence":null}]'::jsonb,
    TRUE
  ),
  (
    'mind_meditation',
    'Mind and meditation',
    'Meditation, mindfulness, breathwork, and adjacent mind-body practices.',
    '[{"source_name":"agent_spec","url":"AGENT_SPEC.md#4-category-taxonomy","trust_tier":"official","seen_at":"2026-06-18T00:00:00Z","source_record_id":"s4","licence":null}]'::jsonb,
    TRUE
  ),
  (
    'spa_thermal',
    'Spa and thermal',
    'Spa, massage, esthetics, steam, thermal, and body treatment services.',
    '[{"source_name":"agent_spec","url":"AGENT_SPEC.md#4-category-taxonomy","trust_tier":"official","seen_at":"2026-06-18T00:00:00Z","source_record_id":"s4","licence":null}]'::jsonb,
    TRUE
  ),
  (
    'nutrition_longevity',
    'Nutrition and longevity',
    'Nutrition, dietitian, longevity, supplement-guided, and health optimization services.',
    '[{"source_name":"agent_spec","url":"AGENT_SPEC.md#4-category-taxonomy","trust_tier":"official","seen_at":"2026-06-18T00:00:00Z","source_record_id":"s4","licence":null}]'::jsonb,
    TRUE
  ),
  (
    'allied_health',
    'Allied health',
    'Physiotherapy, chiropractic, acupuncture, naturopathy, kinesiology, RMT, and practitioner clinics.',
    '[{"source_name":"agent_spec","url":"AGENT_SPEC.md#4-category-taxonomy","trust_tier":"official","seen_at":"2026-06-18T00:00:00Z","source_record_id":"s4","licence":null}]'::jsonb,
    TRUE
  ),
  (
    'womens_health',
    'Women''s health',
    'Women-focused health, maternity, doula, midwifery, and related wellness services.',
    '[{"source_name":"agent_spec","url":"AGENT_SPEC.md#4-category-taxonomy","trust_tier":"official","seen_at":"2026-06-18T00:00:00Z","source_record_id":"s4","licence":null}]'::jsonb,
    TRUE
  ),
  (
    'preventive_diagnostic',
    'Preventive and diagnostic',
    'Diagnostics, labs, screening, imaging, and preventive health services.',
    '[{"source_name":"agent_spec","url":"AGENT_SPEC.md#4-category-taxonomy","trust_tier":"official","seen_at":"2026-06-18T00:00:00Z","source_record_id":"s4","licence":null}]'::jsonb,
    TRUE
  ),
  (
    'mental_health',
    'Mental health',
    'Counselling, psychology, psychotherapy, and adjacent mental-health services.',
    '[{"source_name":"agent_spec","url":"AGENT_SPEC.md#4-category-taxonomy","trust_tier":"official","seen_at":"2026-06-18T00:00:00Z","source_record_id":"s4","licence":null}]'::jsonb,
    TRUE
  ),
  (
    'community_social_wellness',
    'Community and social wellness',
    'Community wellness, social wellness, convening, group wellness, and social club models.',
    '[{"source_name":"agent_spec","url":"AGENT_SPEC.md#4-category-taxonomy","trust_tier":"official","seen_at":"2026-06-18T00:00:00Z","source_record_id":"s4","licence":null}]'::jsonb,
    TRUE
  ),
  (
    'wellness_retail_product',
    'Wellness retail and product',
    'Health food, supplement, wellness retail, and wellness product operators.',
    '[{"source_name":"agent_spec","url":"AGENT_SPEC.md#4-category-taxonomy","trust_tier":"official","seen_at":"2026-06-18T00:00:00Z","source_record_id":"s4","licence":null}]'::jsonb,
    TRUE
  )
ON CONFLICT (category) DO UPDATE SET
  label = EXCLUDED.label,
  description = EXCLUDED.description,
  source_refs = EXCLUDED.source_refs,
  needs_human_review = EXCLUDED.needs_human_review,
  active = TRUE;

CREATE TABLE IF NOT EXISTS naics_category_crosswalk (
  id                 TEXT PRIMARY KEY,
  category           TEXT NOT NULL REFERENCES category_taxonomy(category),
  naics_code         TEXT NOT NULL,
  naics_label        TEXT NOT NULL,
  match_kind         TEXT NOT NULL,
  rationale          TEXT NOT NULL,
  source_refs        JSONB NOT NULL,
  needs_human_review BOOLEAN NOT NULL DEFAULT TRUE,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (category, naics_code)
);

INSERT INTO naics_category_crosswalk (
  id, category, naics_code, naics_label, match_kind, rationale, source_refs, needs_human_review
) VALUES
  (
    'naics_recovery_812190',
    'recovery_contrast_therapy',
    '812190',
    'Other personal care services',
    'primary',
    'Statistics Canada examples include saunas, bath houses, Turkish baths, massage parlours, and non-medical weight-reduction centres; recovery and contrast therapy operators often sit here when not coded as fitness facilities.',
    '[{"source_name":"statcan_naics_2022","url":"https://www23.statcan.gc.ca/imdb/p3VD.pl?CLV=6&CPV=812190&CST=27012022&CVD=1370970&Function=getVD&MLV=6&TVD=1381557","trust_tier":"official","seen_at":"2026-06-18T00:00:00Z","source_record_id":"812190","licence":"Statistics Canada terms"}]'::jsonb,
    TRUE
  ),
  (
    'naics_recovery_713940',
    'recovery_contrast_therapy',
    '713940',
    'Fitness and recreational sports centres',
    'secondary',
    'Health spas without accommodations and fitness/recreation facilities may capture recovery club operators when the licence/business-count source classifies them as recreation facilities.',
    '[{"source_name":"statcan_naics_2022","url":"https://www23.statcan.gc.ca/imdb/p3VD.pl?CLV=6&CPV=713940&CST=27012022&CVD=1370970&Function=getVD&MLV=6&TVD=1381557","trust_tier":"official","seen_at":"2026-06-18T00:00:00Z","source_record_id":"713940","licence":"Statistics Canada terms"}]'::jsonb,
    TRUE
  ),
  (
    'naics_fitness_713940',
    'fitness_movement',
    '713940',
    'Fitness and recreational sports centres',
    'primary',
    'Primary denominator for gyms, fitness centres, athletic clubs, and similar movement facilities.',
    '[{"source_name":"statcan_naics_2022","url":"https://www23.statcan.gc.ca/imdb/p3VD.pl?CLV=6&CPV=713940&CST=27012022&CVD=1370970&Function=getVD&MLV=6&TVD=1381557","trust_tier":"official","seen_at":"2026-06-18T00:00:00Z","source_record_id":"713940","licence":"Statistics Canada terms"}]'::jsonb,
    TRUE
  ),
  (
    'naics_mind_611690',
    'mind_meditation',
    '611690',
    'All other schools and instruction',
    'secondary',
    'Meditation and breathwork studios may be classified as instruction when the business model is class-based rather than clinic-based.',
    '[{"source_name":"statcan_naics_2022","url":"https://www23.statcan.gc.ca/imdb/p3VD.pl?CLV=5&CPV=611690&CST=27012022&CVD=1370970&Function=getVD&MLV=6&TVD=1381557","trust_tier":"official","seen_at":"2026-06-18T00:00:00Z","source_record_id":"611690","licence":"Statistics Canada terms"}]'::jsonb,
    TRUE
  ),
  (
    'naics_spa_812190',
    'spa_thermal',
    '812190',
    'Other personal care services',
    'primary',
    'Spa, sauna, bathhouse, massage, and other personal care examples map most closely to this code for M3 analytics.',
    '[{"source_name":"statcan_naics_2022","url":"https://www23.statcan.gc.ca/imdb/p3VD.pl?CLV=6&CPV=812190&CST=27012022&CVD=1370970&Function=getVD&MLV=6&TVD=1381557","trust_tier":"official","seen_at":"2026-06-18T00:00:00Z","source_record_id":"812190","licence":"Statistics Canada terms"}]'::jsonb,
    TRUE
  ),
  (
    'naics_nutrition_621390',
    'nutrition_longevity',
    '621390',
    'Offices of all other health practitioners',
    'secondary',
    'Dietitian, naturopathic, and longevity-adjacent practitioner services may land under other health practitioners; retail product-heavy operators use the retail mapping instead.',
    '[{"source_name":"statcan_naics_2022","url":"https://www23.statcan.gc.ca/imdb/p3VD.pl?CLV=5&CPV=621390&CST=27012022&CVD=1370970&Function=getVD&MLV=6&TVD=1381557","trust_tier":"official","seen_at":"2026-06-18T00:00:00Z","source_record_id":"621390","licence":"Statistics Canada terms"}]'::jsonb,
    TRUE
  ),
  (
    'naics_allied_621340',
    'allied_health',
    '621340',
    'Offices of physical, occupational, and speech therapists and audiologists',
    'primary',
    'Statistics Canada examples include physiotherapy, occupational therapy, kinesiology, recreational therapy, and related private-practice offices.',
    '[{"source_name":"statcan_naics_2022","url":"https://www23.statcan.gc.ca/imdb/p3VD.pl?CLV=4&CPV=621340&CST=27012022&CVD=1370970&Function=getVD&MLV=6&TVD=1383631","trust_tier":"official","seen_at":"2026-06-18T00:00:00Z","source_record_id":"621340","licence":"Statistics Canada terms"}]'::jsonb,
    TRUE
  ),
  (
    'naics_allied_621390',
    'allied_health',
    '621390',
    'Offices of all other health practitioners',
    'secondary',
    'Catch-all for practitioners not captured by therapy, mental-health, dental, or physician-specific NAICS codes.',
    '[{"source_name":"statcan_naics_2022","url":"https://www23.statcan.gc.ca/imdb/p3VD.pl?CLV=5&CPV=621390&CST=27012022&CVD=1370970&Function=getVD&MLV=6&TVD=1381557","trust_tier":"official","seen_at":"2026-06-18T00:00:00Z","source_record_id":"621390","licence":"Statistics Canada terms"}]'::jsonb,
    TRUE
  ),
  (
    'naics_womens_621410',
    'womens_health',
    '621410',
    'Family planning centres',
    'secondary',
    'Women-focused health services can overlap family planning centres, but this category is broader and requires human review before production analytics.',
    '[{"source_name":"statcan_naics_2022","url":"https://www23.statcan.gc.ca/imdb/p3VD.pl?CLV=5&CPV=621410&CST=27012022&CVD=1370970&Function=getVD&MLV=6&TVD=1381557","trust_tier":"official","seen_at":"2026-06-18T00:00:00Z","source_record_id":"621410","licence":"Statistics Canada terms"}]'::jsonb,
    TRUE
  ),
  (
    'naics_preventive_621510',
    'preventive_diagnostic',
    '621510',
    'Medical and diagnostic laboratories',
    'primary',
    'Primary denominator for lab, diagnostic, and screening-oriented operators.',
    '[{"source_name":"statcan_naics_2022","url":"https://www23.statcan.gc.ca/imdb/p3VD.pl?CLV=5&CPV=621510&CST=27012022&CVD=1370970&Function=getVD&MLV=6&TVD=1381557","trust_tier":"official","seen_at":"2026-06-18T00:00:00Z","source_record_id":"621510","licence":"Statistics Canada terms"}]'::jsonb,
    TRUE
  ),
  (
    'naics_mental_621330',
    'mental_health',
    '621330',
    'Offices of mental health practitioners, except physicians',
    'primary',
    'Primary denominator for counselling, psychology, psychotherapy, and non-physician mental-health practitioner offices.',
    '[{"source_name":"statcan_naics_2022","url":"https://www23.statcan.gc.ca/imdb/p3VD.pl?CLV=5&CPV=621330&CST=27012022&CVD=1370970&Function=getVD&MLV=6&TVD=1381557","trust_tier":"official","seen_at":"2026-06-18T00:00:00Z","source_record_id":"621330","licence":"Statistics Canada terms"}]'::jsonb,
    TRUE
  ),
  (
    'naics_social_813410',
    'community_social_wellness',
    '813410',
    'Civic and social organizations',
    'secondary',
    'Community wellness and convening models may overlap social organizations; commercial social wellness venues may instead map to personal care or fitness.',
    '[{"source_name":"statcan_naics_2022","url":"https://www23.statcan.gc.ca/imdb/p3VD.pl?CLV=5&CPV=813410&CST=27012022&CVD=1370970&Function=getVD&MLV=6&TVD=1381557","trust_tier":"official","seen_at":"2026-06-18T00:00:00Z","source_record_id":"813410","licence":"Statistics Canada terms"}]'::jsonb,
    TRUE
  ),
  (
    'naics_retail_456191',
    'wellness_retail_product',
    '456191',
    'Food (health) supplement stores',
    'primary',
    'Primary retail denominator for supplement and health-product storefronts where available in NAICS 2022 data.',
    '[{"source_name":"statcan_naics_2022","url":"https://www23.statcan.gc.ca/imdb/p3VD.pl?CLV=5&CPV=456191&CST=27012022&CVD=1370970&Function=getVD&MLV=6&TVD=1381557","trust_tier":"official","seen_at":"2026-06-18T00:00:00Z","source_record_id":"456191","licence":"Statistics Canada terms"}]'::jsonb,
    TRUE
  )
ON CONFLICT (category, naics_code) DO UPDATE SET
  naics_label = EXCLUDED.naics_label,
  match_kind = EXCLUDED.match_kind,
  rationale = EXCLUDED.rationale,
  source_refs = EXCLUDED.source_refs,
  needs_human_review = TRUE;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'operator_categories_allowed'
  ) THEN
    ALTER TABLE "operator"
      ADD CONSTRAINT operator_categories_allowed
      CHECK (
        categories <@ ARRAY[
          'recovery_contrast_therapy',
          'fitness_movement',
          'mind_meditation',
          'spa_thermal',
          'nutrition_longevity',
          'allied_health',
          'womens_health',
          'preventive_diagnostic',
          'mental_health',
          'community_social_wellness',
          'wellness_retail_product'
        ]::text[]
      );
  END IF;
END $$;

INSERT INTO source_registry (
  source_name, family, base_url, cadence, licence, cost, trust_tier, geo_rule, phase, rights_notes, enabled
) VALUES
  (
    'statcan_wds',
    'denominator/statistics',
    'https://www.statcan.gc.ca/en/developers/wds',
    'annual/as_released',
    'Statistics Canada open data terms',
    'free',
    'official',
    'Geo-aware denominator records must include StatCan geography code and pass bc_gate when centroid coordinates are present. Vancouver CMA 933 and BC CSDs only for M3.',
    3,
    'needs_review: confirm WDS table/vector selection, attribution text, and production caching policy before launch.',
    TRUE
  ),
  (
    'peer_city_trends_fixture',
    'trend/provider',
    NULL,
    'manual/fixture',
    'internal deterministic fixture, not Google Trends output',
    'free',
    'informal',
    'Peer city benchmark rows are not geo-persisted; provider must label fixture-backed output until a reviewed Trends API/key is available.',
    3,
    'needs_review: stub-backed deterministic fallback only; do not present as Google Trends data until provider terms and API access are approved.',
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

CREATE TABLE IF NOT EXISTS entity_resolution_match (
  id                  TEXT PRIMARY KEY,
  entity_type         TEXT NOT NULL CHECK (entity_type IN ('operator', 'organization', 'person')),
  survivor_id         TEXT NOT NULL,
  duplicate_id        TEXT NOT NULL,
  status              entity_match_status NOT NULL DEFAULT 'candidate',
  confidence_score    REAL NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
  deterministic_rule  TEXT NOT NULL,
  provenance          JSONB NOT NULL,
  source_refs         JSONB NOT NULL,
  reviewed_by         TEXT,
  reviewed_at         TIMESTAMPTZ,
  reversed_at         TIMESTAMPTZ,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (survivor_id <> duplicate_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS entity_resolution_active_duplicate_idx
  ON entity_resolution_match (entity_type, duplicate_id)
  WHERE status IN ('candidate', 'merged');

CREATE TABLE IF NOT EXISTS entity_alias (
  entity_type      TEXT NOT NULL CHECK (entity_type IN ('operator', 'organization', 'person')),
  alias_id         TEXT NOT NULL,
  canonical_id     TEXT NOT NULL,
  match_id         TEXT NOT NULL REFERENCES entity_resolution_match(id),
  active           BOOLEAN NOT NULL DEFAULT TRUE,
  source_refs      JSONB NOT NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  deactivated_at   TIMESTAMPTZ,
  PRIMARY KEY (entity_type, alias_id)
);

CREATE TABLE IF NOT EXISTS statcan_geography (
  geo_code          TEXT PRIMARY KEY,
  geo_level         TEXT NOT NULL,
  geo_name          TEXT NOT NULL,
  parent_geo_code   TEXT,
  geom              GEOGRAPHY(POINT, 4326),
  source_name       TEXT NOT NULL REFERENCES source_registry(source_name),
  source_refs       JSONB NOT NULL,
  confidence_score  REAL NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
  bc_gate_result    JSONB NOT NULL DEFAULT '{}'::jsonb,
  payload           JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS statcan_denominator (
  id                TEXT PRIMARY KEY,
  geo_code          TEXT NOT NULL REFERENCES statcan_geography(geo_code),
  geo_level         TEXT NOT NULL,
  geo_name          TEXT NOT NULL,
  metric            TEXT NOT NULL CHECK (metric IN ('population', 'business_count')),
  category          TEXT REFERENCES category_taxonomy(category),
  naics_code        TEXT,
  value             NUMERIC NOT NULL CHECK (value >= 0),
  unit              TEXT NOT NULL,
  reference_period  TEXT NOT NULL,
  source_name       TEXT NOT NULL REFERENCES source_registry(source_name),
  source_refs       JSONB NOT NULL,
  confidence_score  REAL NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
  payload           JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS statcan_denominator_geo_metric_idx
  ON statcan_denominator (geo_code, metric, category);

CREATE TABLE IF NOT EXISTS opportunity_heatmap_cell (
  id                       TEXT PRIMARY KEY,
  category                 TEXT NOT NULL REFERENCES category_taxonomy(category),
  geo_code                 TEXT NOT NULL REFERENCES statcan_geography(geo_code),
  geo_name                 TEXT NOT NULL,
  geo_level                TEXT NOT NULL,
  geom                     GEOGRAPHY(POINT, 4326),
  supply_count             INT NOT NULL CHECK (supply_count >= 0),
  operator_ids             TEXT[] NOT NULL DEFAULT '{}',
  population               NUMERIC,
  business_count           NUMERIC,
  demand_proxy             REAL NOT NULL,
  low_supply_density       REAL NOT NULL,
  category_growth          REAL NOT NULL,
  target_demo_fit          REAL NOT NULL,
  transit_access           REAL NOT NULL,
  event_community_activity REAL NOT NULL,
  source_confidence        REAL NOT NULL,
  opportunity_score        REAL NOT NULL,
  component_breakdown      JSONB NOT NULL,
  calculation_method       TEXT NOT NULL,
  source_refs              JSONB NOT NULL,
  confidence_score         REAL NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
  trace_payload            JSONB NOT NULL DEFAULT '{}'::jsonb,
  generated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (category, geo_code)
);

CREATE TABLE IF NOT EXISTS opportunity_scorecard (
  id                       TEXT PRIMARY KEY,
  category                 TEXT NOT NULL REFERENCES category_taxonomy(category),
  geo_code                 TEXT NOT NULL REFERENCES statcan_geography(geo_code),
  geo_name                 TEXT NOT NULL,
  opportunity_score        REAL NOT NULL,
  component_breakdown      JSONB NOT NULL,
  source_refs              JSONB NOT NULL,
  confidence_score         REAL NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
  calculation_method       TEXT NOT NULL,
  caveat                   TEXT NOT NULL,
  generated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (category, geo_code)
);

CREATE TABLE IF NOT EXISTS category_velocity (
  id                   TEXT PRIMARY KEY,
  category             TEXT NOT NULL REFERENCES category_taxonomy(category),
  window_days          INT NOT NULL CHECK (window_days IN (30, 90, 180)),
  new_operator_count   INT NOT NULL CHECK (new_operator_count >= 0),
  job_velocity_count   INT NOT NULL CHECK (job_velocity_count >= 0),
  event_velocity_count INT NOT NULL CHECK (event_velocity_count >= 0),
  news_velocity_count  INT NOT NULL CHECK (news_velocity_count >= 0),
  component_breakdown  JSONB NOT NULL,
  source_refs          JSONB NOT NULL,
  confidence_score     REAL NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
  calculated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (category, window_days)
);

ALTER TABLE trend
  ADD COLUMN IF NOT EXISTS confidence_score REAL NOT NULL DEFAULT 0.5,
  ADD COLUMN IF NOT EXISTS is_stub BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS methodology TEXT NOT NULL DEFAULT 'Provider-supplied trend series.',
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE TABLE IF NOT EXISTS person_influence_component (
  person_id                       TEXT PRIMARY KEY REFERENCES person(id),
  institutional_authority         REAL NOT NULL,
  network_centrality              REAL NOT NULL,
  research_or_clinical_leadership REAL NOT NULL,
  media_velocity                  REAL NOT NULL,
  capital_power                   REAL NOT NULL,
  event_convening                 REAL NOT NULL,
  public_reach                    REAL NOT NULL,
  locality_multiplier             REAL NOT NULL,
  recency_decay                   REAL NOT NULL,
  source_confidence               REAL NOT NULL,
  influence_score                 REAL NOT NULL,
  component_breakdown             JSONB NOT NULL,
  explanation                     TEXT NOT NULL,
  methodology_version             TEXT NOT NULL,
  source_refs                     JSONB NOT NULL,
  confidence_score                REAL NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
  calculated_at                   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS entity_graph_node (
  id                TEXT PRIMARY KEY,
  node_type         TEXT NOT NULL CHECK (node_type IN ('person', 'organization', 'operator', 'event')),
  entity_id         TEXT NOT NULL,
  label             TEXT NOT NULL,
  primary_category  TEXT,
  centrality        REAL NOT NULL DEFAULT 0,
  community         INT NOT NULL DEFAULT 0,
  x                 REAL,
  y                 REAL,
  source_refs       JSONB NOT NULL,
  confidence_score  REAL NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
  payload           JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS entity_graph_edge (
  id                TEXT PRIMARY KEY,
  source_node_id    TEXT NOT NULL REFERENCES entity_graph_node(id),
  target_node_id    TEXT NOT NULL REFERENCES entity_graph_node(id),
  edge_type         TEXT NOT NULL CHECK (
    edge_type IN (
      'founder',
      'employee',
      'advisor',
      'investor',
      'speaker',
      'co_author',
      'mentioned_with',
      'affiliated_with',
      'operator_of'
    )
  ),
  weight            REAL NOT NULL DEFAULT 1,
  source_refs       JSONB NOT NULL,
  confidence_score  REAL NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
  payload           JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (source_node_id, target_node_id, edge_type)
);

CREATE INDEX IF NOT EXISTS entity_graph_edge_source_idx ON entity_graph_edge (source_node_id);
CREATE INDEX IF NOT EXISTS entity_graph_edge_target_idx ON entity_graph_edge (target_node_id);
