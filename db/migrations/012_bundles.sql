CREATE TABLE IF NOT EXISTS bundle (
  id                   TEXT PRIMARY KEY,
  label                TEXT NOT NULL,
  slug                 TEXT NOT NULL UNIQUE,
  bundle_score         REAL NOT NULL CHECK (bundle_score >= 0 AND bundle_score <= 1),
  components           JSONB NOT NULL DEFAULT '{}'::jsonb,
  geography            JSONB NOT NULL DEFAULT '{}'::jsonb,
  member_count         INT NOT NULL CHECK (member_count >= 0),
  supporting_signals   JSONB NOT NULL DEFAULT '[]'::jsonb,
  source_refs          JSONB NOT NULL,
  confidence_score     REAL NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
  generated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (jsonb_typeof(components) = 'object'),
  CHECK (jsonb_typeof(geography) = 'object'),
  CHECK (jsonb_typeof(supporting_signals) = 'array'),
  CHECK (jsonb_typeof(source_refs) = 'array'),
  CHECK (jsonb_array_length(source_refs) > 0)
);

CREATE INDEX IF NOT EXISTS bundle_score_idx
  ON bundle (bundle_score DESC, label);

CREATE TABLE IF NOT EXISTS bundle_operator_membership (
  bundle_id            TEXT NOT NULL REFERENCES bundle(id) ON DELETE CASCADE,
  operator_id          TEXT NOT NULL REFERENCES "operator"(id) ON DELETE CASCADE,
  match_reasons        JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_refs          JSONB NOT NULL,
  confidence_score     REAL NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
  generated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (bundle_id, operator_id),
  CHECK (jsonb_typeof(match_reasons) = 'object'),
  CHECK (jsonb_typeof(source_refs) = 'array'),
  CHECK (jsonb_array_length(source_refs) > 0)
);

CREATE INDEX IF NOT EXISTS bundle_operator_membership_operator_idx
  ON bundle_operator_membership (operator_id);

CREATE TABLE IF NOT EXISTS bundle_person (
  bundle_id            TEXT NOT NULL REFERENCES bundle(id) ON DELETE CASCADE,
  person_id            TEXT NOT NULL REFERENCES person(id) ON DELETE CASCADE,
  rank                 INT NOT NULL CHECK (rank > 0),
  influence_score      REAL,
  why_appears          TEXT NOT NULL,
  source_refs          JSONB NOT NULL,
  confidence_score     REAL NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
  generated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (bundle_id, person_id),
  CHECK (jsonb_typeof(source_refs) = 'array'),
  CHECK (jsonb_array_length(source_refs) > 0)
);

CREATE INDEX IF NOT EXISTS bundle_person_rank_idx
  ON bundle_person (bundle_id, rank);
