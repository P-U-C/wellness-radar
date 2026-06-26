ALTER TABLE "operator"
  ADD COLUMN IF NOT EXISTS is_mobile BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS service_area JSONB;

ALTER TABLE "operator"
  DROP CONSTRAINT IF EXISTS operator_service_area_object;

ALTER TABLE "operator"
  ADD CONSTRAINT operator_service_area_object
  CHECK (service_area IS NULL OR jsonb_typeof(service_area) = 'object');

ALTER TABLE organization
  ADD COLUMN IF NOT EXISTS location JSONB,
  ADD COLUMN IF NOT EXISTS headcount INT,
  ADD COLUMN IF NOT EXISTS industry TEXT,
  ADD COLUMN IF NOT EXISTS industry_code TEXT,
  ADD COLUMN IF NOT EXISTS firmographic_source_refs JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE organization
  DROP CONSTRAINT IF EXISTS organization_location_object;

ALTER TABLE organization
  ADD CONSTRAINT organization_location_object
  CHECK (location IS NULL OR jsonb_typeof(location) = 'object');

ALTER TABLE organization
  DROP CONSTRAINT IF EXISTS organization_firmographic_source_refs_array;

ALTER TABLE organization
  ADD CONSTRAINT organization_firmographic_source_refs_array
  CHECK (jsonb_typeof(firmographic_source_refs) = 'array');

ALTER TABLE opportunity_proposition
  ADD COLUMN IF NOT EXISTS primary_bundles TEXT[] NOT NULL DEFAULT '{}';

CREATE TABLE IF NOT EXISTS category_classification_rule (
  id                 TEXT PRIMARY KEY,
  category           TEXT NOT NULL REFERENCES category_taxonomy(category),
  match_scope        TEXT NOT NULL,
  keywords           TEXT[] NOT NULL,
  precision_notes    TEXT NOT NULL,
  source_refs        JSONB NOT NULL,
  active             BOOLEAN NOT NULL DEFAULT TRUE,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (jsonb_typeof(source_refs) = 'array'),
  CHECK (jsonb_array_length(source_refs) > 0)
);

WITH refs AS (
  SELECT
    '[{"source_name":"persona_gap_review","url":"docs/persona-gap-review/GAP_REPORT.md#G12","trust_tier":"informal","seen_at":"2026-06-26T00:00:00Z","source_record_id":"G12","licence":null}]'::jsonb
    AS gap_refs
)
INSERT INTO category_taxonomy (
  category,
  label,
  description,
  source_refs,
  needs_human_review,
  active
)
SELECT *
FROM (
  VALUES
    (
      'aesthetics_medspa',
      'Aesthetics and med-spa',
      'Medical aesthetics, injectables, skin clinics, laser, and med-spa operators.',
      (SELECT gap_refs FROM refs),
      TRUE,
      TRUE
    ),
    (
      'womens_health',
      'Women''s health',
      'Pregnancy, prenatal, postnatal, pelvic floor, lactation, doula, midwifery, and women-focused wellness services.',
      (SELECT gap_refs FROM refs),
      TRUE,
      TRUE
    ),
    (
      'social_hospitality',
      'Social hospitality wellness',
      'Sober-social, wellness cafe, coworking wellness, and third-place wellness concepts.',
      (SELECT gap_refs FROM refs),
      TRUE,
      TRUE
    ),
    (
      'recovery_modalities',
      'Recovery modalities',
      'Cryo, compression, percussion, assisted stretch, and mobility recovery services.',
      (SELECT gap_refs FROM refs),
      TRUE,
      TRUE
    )
) AS seeded(category, label, description, source_refs, needs_human_review, active)
ON CONFLICT (category) DO UPDATE SET
  label = EXCLUDED.label,
  description = EXCLUDED.description,
  source_refs = EXCLUDED.source_refs,
  needs_human_review = EXCLUDED.needs_human_review,
  active = TRUE;

WITH refs AS (
  SELECT
    '[{"source_name":"persona_gap_review","url":"docs/persona-gap-review/GAP_REPORT.md#G12","trust_tier":"informal","seen_at":"2026-06-26T00:00:00Z","source_record_id":"G12","licence":null}]'::jsonb
    AS gap_refs
)
INSERT INTO category_classification_rule (
  id,
  category,
  match_scope,
  keywords,
  precision_notes,
  source_refs
) VALUES
  (
    'p2b_rule_aesthetics_medspa',
    'aesthetics_medspa',
    'operator name, licence type/subtype, source tags',
    ARRAY[
      'medical aesthetics',
      'medspa',
      'med spa',
      'botox',
      'injectable',
      'injectables',
      'filler',
      'fillers',
      'cosmetic clinic',
      'skin clinic',
      'laser clinic',
      'microneedling'
    ]::text[],
    'High precision only: plain spa, esthetic, or skin text is insufficient without medical-aesthetics or procedure evidence.',
    (SELECT gap_refs FROM refs)
  ),
  (
    'p2b_rule_womens_health',
    'womens_health',
    'operator name, licence type/subtype, source tags',
    ARRAY[
      'pregnancy',
      'prenatal',
      'postnatal',
      'postpartum',
      'perinatal',
      'pelvic floor',
      'lactation',
      'doula',
      'midwife',
      'midwifery',
      'maternity'
    ]::text[],
    'Women-focused category uses care-stage terms rather than broad health or fitness labels.',
    (SELECT gap_refs FROM refs)
  ),
  (
    'p2b_rule_social_hospitality',
    'social_hospitality',
    'operator name, licence type/subtype, source tags',
    ARRAY[
      'sober social',
      'sober club',
      'sober bar',
      'sober curious',
      'wellness cafe',
      'wellness coworking',
      'coworking wellness',
      'social club',
      'third place wellness'
    ]::text[],
    'Plain cafe or coworking terms are not enough; the source text must carry wellness, sober, or social-club evidence.',
    (SELECT gap_refs FROM refs)
  ),
  (
    'p2b_rule_recovery_modalities',
    'recovery_modalities',
    'operator name, licence type/subtype, source tags',
    ARRAY[
      'cryo',
      'cryotherapy',
      'normatec',
      'compression therapy',
      'compression boots',
      'percussion therapy',
      'mobility',
      'sports recovery',
      'assisted stretch'
    ]::text[],
    'Recovery modality requires specific equipment or service modality terms; addiction or mental-health recovery terms are excluded in application hygiene rules.',
    (SELECT gap_refs FROM refs)
  )
ON CONFLICT (id) DO UPDATE SET
  category = EXCLUDED.category,
  match_scope = EXCLUDED.match_scope,
  keywords = EXCLUDED.keywords,
  precision_notes = EXCLUDED.precision_notes,
  source_refs = EXCLUDED.source_refs,
  active = TRUE;

INSERT INTO naics_category_crosswalk (
  id,
  category,
  naics_code,
  naics_label,
  match_kind,
  rationale,
  source_refs,
  needs_human_review
) VALUES
  (
    'naics_aesthetics_medspa_812190',
    'aesthetics_medspa',
    '812190',
    'Other personal care services',
    'secondary',
    'Medical aesthetics and med-spa operators may be counted under broad personal care services, but procedure-level demand and regulated status are not inferred from this aggregate.',
    '[{"source_name":"statcan_naics_2022","url":"https://www23.statcan.gc.ca/imdb/p3VD.pl?CLV=6&CPV=812190&CST=27012022&CVD=1370970&Function=getVD&MLV=6&TVD=1381557","trust_tier":"official","seen_at":"2026-06-26T00:00:00Z","source_record_id":"812190","licence":"Statistics Canada terms"}]'::jsonb,
    TRUE
  ),
  (
    'naics_recovery_modalities_713940',
    'recovery_modalities',
    '713940',
    'Fitness and recreational sports centres',
    'secondary',
    'Cryo, compression, percussion, mobility, and athlete-recovery operators frequently co-locate with fitness/recreation but require source-text category evidence.',
    '[{"source_name":"statcan_naics_2022","url":"https://www23.statcan.gc.ca/imdb/p3VD.pl?CLV=6&CPV=713940&CST=27012022&CVD=1370970&Function=getVD&MLV=6&TVD=1381557","trust_tier":"official","seen_at":"2026-06-26T00:00:00Z","source_record_id":"713940","licence":"Statistics Canada terms"}]'::jsonb,
    TRUE
  ),
  (
    'naics_social_hospitality_813410',
    'social_hospitality',
    '813410',
    'Civic and social organizations',
    'secondary',
    'Sober-social, cafe, and coworking wellness concepts are blended hospitality/community models; plain cafes or coworking locations are not included without wellness or sober-social evidence.',
    '[{"source_name":"statcan_naics_2022","url":"https://www23.statcan.gc.ca/imdb/p3VD.pl?CLV=5&CPV=813410&CST=27012022&CVD=1370970&Function=getVD&MLV=6&TVD=1381557","trust_tier":"official","seen_at":"2026-06-26T00:00:00Z","source_record_id":"813410","licence":"Statistics Canada terms"}]'::jsonb,
    TRUE
  )
ON CONFLICT (category, naics_code) DO UPDATE SET
  naics_label = EXCLUDED.naics_label,
  match_kind = EXCLUDED.match_kind,
  rationale = EXCLUDED.rationale,
  source_refs = EXCLUDED.source_refs,
  needs_human_review = TRUE;

ALTER TABLE "operator"
  DROP CONSTRAINT IF EXISTS operator_categories_allowed;

ALTER TABLE "operator"
  ADD CONSTRAINT operator_categories_allowed
  CHECK (
    categories <@ ARRAY[
      'recovery_contrast_therapy',
      'fitness_movement',
      'racquet_court_sports',
      'climbing',
      'combat_sports',
      'aquatics',
      'ice_sports',
      'field_track_sports',
      'public_recreation',
      'mind_meditation',
      'spa_thermal',
      'aesthetics_medspa',
      'nutrition_longevity',
      'allied_health',
      'womens_health',
      'social_hospitality',
      'recovery_modalities',
      'preventive_diagnostic',
      'mental_health',
      'community_social_wellness',
      'wellness_retail_product'
    ]::text[]
  );

UPDATE "operator" op
SET categories = ARRAY(
  SELECT DISTINCT category
  FROM unnest(
    array_remove(
      array_remove(
        array_remove(
          array_remove(op.categories, 'fitness_movement'),
          'public_recreation'
        ),
        'spa_thermal'
      ),
      'allied_health'
    ) || ARRAY['aesthetics_medspa']::text[]
  ) AS category
)
WHERE lower(op.name) ~
  '(^|[^a-z0-9])(medical aesthetics|medspa|med spa|botox|injectable|injectables|filler|fillers|cosmetic clinic|skin clinic|laser clinic|microneedling)([^a-z0-9]|$)'
  AND jsonb_array_length(op.source_refs) > 0;

UPDATE "operator" op
SET categories = ARRAY(
  SELECT DISTINCT category
  FROM unnest(
    array_remove(
      array_remove(op.categories, 'fitness_movement'),
      'public_recreation'
    ) || ARRAY['womens_health']::text[]
  ) AS category
)
WHERE lower(op.name) ~
  '(^|[^a-z0-9])(pregnancy|prenatal|postnatal|postpartum|perinatal|pelvic floor|lactation|doula|midwife|midwifery|maternity)([^a-z0-9]|$)'
  AND jsonb_array_length(op.source_refs) > 0;

UPDATE "operator" op
SET categories = ARRAY(
  SELECT DISTINCT category
  FROM unnest(op.categories || ARRAY['recovery_modalities']::text[]) AS category
)
WHERE lower(op.name) ~
  '(^|[^a-z0-9])(cryo|cryotherapy|normatec|compression therapy|compression boots|percussion therapy|mobility|sports recovery|assisted stretch)([^a-z0-9]|$)'
  AND lower(op.name) !~ '(^|[^a-z0-9])(addiction|drug|alcohol|rehab|rehabilitation)([^a-z0-9]|$)'
  AND jsonb_array_length(op.source_refs) > 0;

UPDATE "operator" op
SET categories = ARRAY(
  SELECT DISTINCT category
  FROM unnest(op.categories || ARRAY['social_hospitality']::text[]) AS category
)
WHERE lower(op.name) ~
  '(^|[^a-z0-9])(sober social|sober club|sober bar|sober curious|wellness cafe|wellness coworking|coworking wellness|social club|third place wellness)([^a-z0-9]|$)'
  AND jsonb_array_length(op.source_refs) > 0;

UPDATE "operator" op
SET
  venue_class = 'commercial_wellness',
  operator_class = CASE
    WHEN op.categories && ARRAY['aesthetics_medspa', 'womens_health']::text[]
      THEN 'medical_adjacent'
    WHEN op.categories && ARRAY['recovery_modalities', 'social_hospitality']::text[]
      THEN 'personal_services'
    ELSE op.operator_class
  END,
  regulated = op.regulated OR op.categories && ARRAY['aesthetics_medspa', 'womens_health']::text[],
  operator_class_reason = jsonb_build_object(
    'methodology_version', 'p2b_taxonomy_sql_backfill_v1',
    'note', 'P2B taxonomy backfill for med-spa, women''s health, social hospitality, and recovery modalities.',
    'source_refs', op.source_refs
  ),
  venue_class_reason = jsonb_build_object(
    'methodology_version', 'p2b_taxonomy_sql_backfill_v1',
    'note', 'P2B commercial wellness taxonomy categories are not municipal recreation.',
    'source_refs', op.source_refs
  )
WHERE op.categories && ARRAY[
  'aesthetics_medspa',
  'womens_health',
  'recovery_modalities',
  'social_hospitality'
]::text[];

UPDATE "operator" op
SET
  is_mobile = TRUE,
  service_area = COALESCE(
    op.service_area,
    jsonb_build_object(
      'type', 'mobile_unspecified',
      'label', 'Mobile service area not specified in source text',
      'radius_km', NULL,
      'methodology_version', 'p2b_service_area_sql_backfill_v1'
    )
  )
WHERE lower(op.name) ~ '(^|[^a-z0-9])(mobile|at home|in home|home visit|house call|on site|onsite)([^a-z0-9]|$)'
  AND jsonb_array_length(op.source_refs) > 0;

CREATE INDEX IF NOT EXISTS operator_is_mobile_idx
  ON "operator" (is_mobile);

CREATE INDEX IF NOT EXISTS operator_service_area_gin_idx
  ON "operator" USING GIN (service_area);

CREATE INDEX IF NOT EXISTS opportunity_proposition_primary_bundles_gin_idx
  ON opportunity_proposition USING GIN (primary_bundles);
