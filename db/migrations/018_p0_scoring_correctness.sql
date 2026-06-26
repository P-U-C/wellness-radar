INSERT INTO source_registry (
  source_name, family, base_url, cadence, licence, cost, trust_tier, geo_rule, phase,
  rights_notes, enabled
) VALUES
  (
    'city_vancouver_census_local_area_profiles_2016',
    'denominator/open_data',
    'https://opendata.vancouver.ca/explore/dataset/census-local-area-profiles-2016/',
    'static/reviewed',
    'Statistics Canada Census 2016 custom profile via City of Vancouver Open Data',
    'free',
    'official',
    'City of Vancouver local-area population values apply only to Vancouver local areas; derived rows still pass bc_gate before persistence.',
    5,
    'City of Vancouver Open Data Portal publishes Census local area profiles 2016 as Statistics Canada custom profiles for the City''s 22 Local Areas. Reproduce with credit to Statistics Canada, Census 2016. Used only as aggregate neighborhood population denominators.',
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

DELETE FROM opportunity_proposition prop
USING opportunity_heatmap_cell cell
WHERE prop.heatmap_cell_id = cell.id
  AND cell.geo_level = 'neighborhood';

DELETE FROM opportunity_scorecard
WHERE geo_level = 'neighborhood';

DELETE FROM opportunity_heatmap_cell
WHERE geo_level = 'neighborhood';

DELETE FROM statcan_geography
WHERE source_name = 'derived_neighborhood_analytics';
