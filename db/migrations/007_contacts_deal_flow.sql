CREATE TABLE IF NOT EXISTS operator_contact (
  id                TEXT PRIMARY KEY,
  operator_id       TEXT NOT NULL REFERENCES "operator"(id) ON DELETE CASCADE,
  contact_type      TEXT NOT NULL CHECK (contact_type IN ('phone', 'email', 'website', 'social')),
  value             TEXT NOT NULL,
  normalized_value  TEXT NOT NULL,
  platform          TEXT,
  source_ref        JSONB NOT NULL,
  confidence_score  REAL NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
  first_seen_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (jsonb_typeof(source_ref) = 'object'),
  CHECK (source_ref ? 'source_name')
);

CREATE UNIQUE INDEX IF NOT EXISTS operator_contact_unique_idx
  ON operator_contact (operator_id, contact_type, normalized_value, COALESCE(platform, ''));

CREATE INDEX IF NOT EXISTS operator_contact_operator_idx
  ON operator_contact (operator_id, contact_type);

ALTER TABLE export_snapshot
  DROP CONSTRAINT IF EXISTS export_snapshot_snapshot_type_check;

ALTER TABLE export_snapshot
  ADD CONSTRAINT export_snapshot_snapshot_type_check
  CHECK (snapshot_type IN ('operators', 'signals', 'graph', 'leads', 'people'));
