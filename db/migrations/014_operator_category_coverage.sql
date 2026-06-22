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
      'nutrition_longevity',
      'allied_health',
      'womens_health',
      'preventive_diagnostic',
      'mental_health',
      'community_social_wellness',
      'wellness_retail_product'
    ]::text[]
  );
