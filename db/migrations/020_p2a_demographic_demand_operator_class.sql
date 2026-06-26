ALTER TABLE "operator"
  ADD COLUMN IF NOT EXISTS operator_class TEXT NOT NULL DEFAULT 'unknown',
  ADD COLUMN IF NOT EXISTS regulated BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS operator_class_reason JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE "operator"
  DROP CONSTRAINT IF EXISTS operator_class_allowed;

ALTER TABLE "operator"
  ADD CONSTRAINT operator_class_allowed
  CHECK (
    operator_class IN (
      'medical_adjacent',
      'fitness',
      'retail',
      'personal_services',
      'public_recreation',
      'unknown'
    )
  );

UPDATE "operator" op
SET
  operator_class = CASE
    WHEN coalesce(op.categories, ARRAY[]::text[]) && ARRAY[
      'allied_health',
      'mental_health',
      'nutrition_longevity',
      'preventive_diagnostic',
      'womens_health'
    ]::text[]
    OR lower(coalesce(op.name, '')) ~
      '(^|[^a-z0-9])(medical aesthetics|medical|clinic|injectable|injectables|botox|filler|fillers|iv|infusion|diagnostic|laboratory|rmt|physio|physiotherapy|chiro|naturopath|acupuncture)([^a-z0-9]|$)'
    THEN 'medical_adjacent'
    WHEN coalesce(op.categories, ARRAY[]::text[]) && ARRAY[
      'climbing',
      'combat_sports',
      'fitness_movement',
      'mind_meditation'
    ]::text[]
    OR lower(coalesce(op.name, '')) ~
      '(^|[^a-z0-9])(fitness|gym|training|strength|crossfit|boxing|kickboxing|martial arts|yoga|pilates|barre)([^a-z0-9]|$)'
    THEN 'fitness'
    WHEN coalesce(op.categories, ARRAY[]::text[]) && ARRAY['wellness_retail_product']::text[]
    OR lower(coalesce(op.name, '')) ~
      '(^|[^a-z0-9])(retail|supplement|health food|vitamin store|natural product)([^a-z0-9]|$)'
    THEN 'retail'
    WHEN coalesce(op.categories, ARRAY[]::text[]) && ARRAY[
      'recovery_contrast_therapy',
      'spa_thermal'
    ]::text[]
    OR lower(coalesce(op.name, '')) ~
      '(^|[^a-z0-9])(spa|sauna|massage|thermal|steam|float|cold plunge|contrast)([^a-z0-9]|$)'
    THEN 'personal_services'
    WHEN coalesce(op.categories, ARRAY[]::text[]) && ARRAY[
      'public_recreation',
      'field_track_sports',
      'racquet_court_sports',
      'aquatics',
      'ice_sports'
    ]::text[]
    THEN 'public_recreation'
    ELSE 'unknown'
  END,
  regulated = (
    coalesce(op.categories, ARRAY[]::text[]) && ARRAY[
      'allied_health',
      'mental_health',
      'nutrition_longevity',
      'preventive_diagnostic',
      'womens_health'
    ]::text[]
    OR lower(coalesce(op.name, '')) ~
      '(^|[^a-z0-9])(medical aesthetics|medical|clinic|injectable|injectables|botox|filler|fillers|iv|infusion|diagnostic|laboratory|rmt|physio|physiotherapy|chiro|naturopath|acupuncture)([^a-z0-9]|$)'
  ),
  operator_class_reason = jsonb_build_object(
    'methodology_version', 'operator_class_sql_backfill_v1',
    'note', 'Initial deterministic backfill; venue_classification analytics job refreshes source/category/tag evidence.',
    'source_refs', op.source_refs
  )
WHERE op.operator_class = 'unknown'
   OR op.operator_class IS NULL
   OR op.operator_class_reason = '{}'::jsonb;

UPDATE "operator" op
SET
  venue_class = 'commercial_wellness',
  venue_class_reason = jsonb_build_object(
    'methodology_version', 'venue_class_sql_backfill_p2a',
    'note', 'Medical-adjacent operator names and regulated categories are commercial wellness, not public recreation.',
    'source_refs', op.source_refs
  )
WHERE op.operator_class = 'medical_adjacent'
  AND op.venue_class = 'unknown';

CREATE INDEX IF NOT EXISTS operator_operator_class_idx
  ON "operator" (operator_class);

CREATE INDEX IF NOT EXISTS operator_regulated_idx
  ON "operator" (regulated);
