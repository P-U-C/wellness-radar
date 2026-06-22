ALTER TABLE "operator"
  ADD COLUMN IF NOT EXISTS venue_class TEXT NOT NULL DEFAULT 'unknown',
  ADD COLUMN IF NOT EXISTS venue_class_reason JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE bundle
  ADD COLUMN IF NOT EXISTS venue_class TEXT NOT NULL DEFAULT 'commercial_wellness';

ALTER TABLE "operator"
  DROP CONSTRAINT IF EXISTS operator_venue_class_allowed;

ALTER TABLE "operator"
  ADD CONSTRAINT operator_venue_class_allowed
  CHECK (venue_class IN ('commercial_wellness', 'public_recreation', 'unknown'));

ALTER TABLE bundle
  DROP CONSTRAINT IF EXISTS bundle_venue_class_allowed;

ALTER TABLE bundle
  ADD CONSTRAINT bundle_venue_class_allowed
  CHECK (venue_class IN ('commercial_wellness', 'public_recreation', 'unknown'));

UPDATE "operator" op
SET
  venue_class = CASE
    WHEN EXISTS (
      SELECT 1
      FROM jsonb_array_elements(op.source_refs) AS ref
      WHERE ref->>'source_name' IN ('city_vancouver_business_licences', 'manual_seed')
    )
    THEN 'commercial_wellness'
    WHEN EXISTS (
      SELECT 1
      FROM jsonb_array_elements(op.source_refs) AS ref
      WHERE ref->>'source_name' LIKE 'municipal_facilities%'
    )
    THEN 'public_recreation'
    WHEN categories && ARRAY[
      'recovery_contrast_therapy',
      'fitness_movement',
      'climbing',
      'combat_sports',
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
    AND NOT categories && ARRAY[
      'public_recreation',
      'field_track_sports',
      'racquet_court_sports',
      'aquatics',
      'ice_sports'
    ]::text[]
    THEN 'commercial_wellness'
    WHEN categories && ARRAY[
      'public_recreation',
      'field_track_sports',
      'racquet_court_sports',
      'aquatics',
      'ice_sports'
    ]::text[]
    THEN 'public_recreation'
    WHEN lower(op.name) ~
      '(sauna|spa|wellness|recovery|cold plunge|contrast|yoga|pilates|gym|fitness|massage|physio|longevity|infusion|iv|clinic|crossfit|boxing)'
    THEN 'commercial_wellness'
    WHEN lower(op.name) ~
      '(park|community centre|community center|recreation centre|recreation center|field|court|pitch|track|pool|rink|arena|stadium)'
    THEN 'public_recreation'
    ELSE 'unknown'
  END,
  venue_class_reason = jsonb_build_object(
    'methodology_version', 'venue_class_sql_backfill_v1',
    'note', 'Initial deterministic backfill; analytics job refreshes source/tag evidence.'
  )
WHERE op.venue_class = 'unknown'
   OR op.venue_class IS NULL
   OR op.venue_class_reason = '{}'::jsonb;

WITH bundle_class_counts AS (
  SELECT
    bom.bundle_id,
    count(*) FILTER (WHERE op.venue_class = 'commercial_wellness') AS commercial_count,
    count(*) FILTER (WHERE op.venue_class = 'public_recreation') AS public_count,
    count(*) FILTER (WHERE op.venue_class = 'unknown') AS unknown_count
  FROM bundle_operator_membership bom
  JOIN "operator" op ON op.id = bom.operator_id
  GROUP BY bom.bundle_id
)
UPDATE bundle b
SET venue_class = CASE
  WHEN counts.commercial_count > counts.public_count THEN 'commercial_wellness'
  WHEN counts.public_count > 0 THEN 'public_recreation'
  WHEN counts.unknown_count > 0 THEN 'unknown'
  ELSE b.venue_class
END
FROM bundle_class_counts counts
WHERE counts.bundle_id = b.id;

CREATE INDEX IF NOT EXISTS operator_venue_class_idx
  ON "operator" (venue_class);

CREATE INDEX IF NOT EXISTS bundle_venue_class_score_idx
  ON bundle (venue_class, bundle_score DESC, label);
