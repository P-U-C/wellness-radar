INSERT INTO source_registry (
  source_name,
  family,
  base_url,
  cadence,
  licence,
  cost,
  trust_tier,
  geo_rule,
  phase,
  rights_notes,
  enabled
) VALUES
  (
    'city_vancouver_building_permits',
    'signal/permit',
    'https://opendata.vancouver.ca/explore/dataset/issued-building-permits/',
    'weekly',
    'City of Vancouver Open Data Portal terms',
    'free',
    'official',
    'Issued building permits are City of Vancouver, BC records; every geocoded permit signal must pass bc_gate before persistence.',
    2,
    'City of Vancouver issued building permits are published on the Open Data Portal under the portal licence/terms. Terms URL: https://opendata.vancouver.ca/pages/licence/. Attribution required; records are used only as supply-pipeline signals, not as operator truth.',
    TRUE
  ),
  (
    'municipal_facilities_new_westminster',
    'directory/regulatory',
    'https://data-60320-newwestcity.opendata.arcgis.com/datasets/newwestcity::business-licenses-all',
    'weekly',
    'Open Government Licence - New Westminster',
    'free',
    'official',
    'New Westminster business licence records only; address text or coordinates must pass bc_gate before persistence.',
    2,
    'City of New Westminster ArcGIS Hub business licence data is public municipal open data. Licence/terms are exposed through the New Westminster open data portal and ArcGIS Hub distribution. Terms URL: https://data-60320-newwestcity.opendata.arcgis.com/.',
    TRUE
  ),
  (
    'municipal_facilities_delta',
    'directory/regulatory',
    'https://opendata-deltabc.hub.arcgis.com/datasets/a77ef0a02cc14bf1b6d5dd8e66991784_0',
    'weekly',
    'Open Government Licence - Delta',
    'free',
    'official',
    'Delta business licence records only; address text or coordinates must pass bc_gate before persistence.',
    2,
    'City of Delta ArcGIS Hub business licence data is public municipal open data. Licence/terms are exposed through the Delta Open Data Hub and ArcGIS Hub distribution. Terms URL: https://opendata-deltabc.hub.arcgis.com/.',
    TRUE
  ),
  (
    'municipal_facilities_north_vancouver',
    'directory/public_recreation',
    'https://geoweb.dnv.org/arcgis/rest/services/Basemap_ParksAppV2/MapServer/0',
    'weekly',
    'Open Government Licence - North Vancouver',
    'free',
    'official',
    'District of North Vancouver parks/recreation records only; every geocoded record must pass bc_gate before persistence.',
    2,
    'District of North Vancouver GEOweb publishes open data under the Open Government Licence - North Vancouver, with attribution statement "Contains information licensed under the Open Government Licence - North Vancouver." Terms URL: https://geoweb.dnv.org/data/.',
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
  cadence = 'semi_annual/as_released',
  licence = 'Statistics Canada Open Licence',
  rights_notes = 'Statistics Canada WDS official aggregate data. Includes WDS getFullTableDownloadCSV Table 33-10-0766-01 Canadian Business Counts by CSD, NAICS and employment size, plus existing population/business-count denominators. Terms URL: https://www.statcan.gc.ca/en/reference/licence. Cache retained only to avoid re-downloading unchanged official outputs.',
  enabled = TRUE,
  updated_at = now()
WHERE source_name = 'statcan_wds';

UPDATE source_registry
SET
  licence = 'BC Gov public registry access terms',
  rights_notes = 'OrgBook BC public topic search API is used only for enrichment against existing source-backed operators; inactive=false and latest=true are sent, and only confident name matches attach registration IDs. Terms URL: https://orgbook.gov.bc.ca/.',
  enabled = TRUE,
  updated_at = now()
WHERE source_name = 'orgbook_bc';

UPDATE source_registry
SET
  family = 'denominator/context',
  base_url = 'https://catalogue.data.gov.bc.ca/dataset/number-of-businesses',
  cadence = 'annual/as_released',
  licence = 'Open Government Licence - British Columbia',
  geo_rule = 'BC Stats Number of Businesses rows are filtered to Metro Vancouver CSDs; text geography must pass bc_gate before persistence.',
  rights_notes = 'BC Data Catalogue Number of Businesses dataset is licensed under the Open Government Licence - British Columbia. Terms URL: https://www2.gov.bc.ca/gov/content/data/open-data/open-government-licence-bc. Records are official aggregate business-location counts, not operator records.',
  enabled = TRUE,
  updated_at = now()
WHERE source_name = 'bc_data_catalogue';
