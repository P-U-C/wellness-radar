WITH source_backed_operators AS (
  SELECT
    op.id,
    op.phone,
    op.website,
    op.social_links,
    op.confidence_score,
    op.source_refs,
    COALESCE(
      (
        SELECT ref
        FROM jsonb_array_elements(op.source_refs) AS ref
        WHERE ref->>'source_name' IN (
          'osm_overpass',
          'city_vancouver_business_licences',
          'manual_seed',
          'orgbook_bc'
        )
        ORDER BY
          CASE ref->>'source_name'
            WHEN 'city_vancouver_business_licences' THEN 0
            WHEN 'osm_overpass' THEN 1
            WHEN 'manual_seed' THEN 2
            ELSE 3
          END
        LIMIT 1
      ),
      op.source_refs->0
    ) AS fallback_source_ref
  FROM "operator" op
  WHERE jsonb_typeof(op.source_refs) = 'array'
    AND jsonb_array_length(op.source_refs) > 0
),
operator_field_values AS (
  SELECT
    op.id AS operator_id,
    contact.contact_type,
    contact.raw_value,
    contact.platform,
    op.fallback_source_ref AS source_ref,
    LEAST(GREATEST(op.confidence_score, 0), 1) AS confidence_score
  FROM source_backed_operators op
  CROSS JOIN LATERAL (
    VALUES
      ('phone', op.phone, NULL::text),
      ('website', op.website, NULL::text)
  ) AS contact(contact_type, raw_value, platform)
  WHERE NULLIF(trim(contact.raw_value), '') IS NOT NULL

  UNION ALL

  SELECT
    op.id AS operator_id,
    'social' AS contact_type,
    social.value AS raw_value,
    social.key AS platform,
    op.fallback_source_ref AS source_ref,
    LEAST(GREATEST(op.confidence_score, 0), 1) AS confidence_score
  FROM source_backed_operators op
  CROSS JOIN LATERAL jsonb_each_text(
    CASE
      WHEN jsonb_typeof(op.social_links) = 'object' THEN op.social_links
      ELSE '{}'::jsonb
    END
  ) AS social(key, value)
  WHERE NULLIF(trim(social.value), '') IS NOT NULL
),
raw_payload_values AS (
  SELECT DISTINCT
    op.id AS operator_id,
    contact.contact_type,
    contact.raw_value,
    contact.platform,
    ref AS source_ref,
    CASE ref->>'source_name'
      WHEN 'city_vancouver_business_licences' THEN 0.86
      WHEN 'osm_overpass' THEN 0.76
      ELSE LEAST(GREATEST(op.confidence_score, 0), 1)
    END AS confidence_score
  FROM source_backed_operators op
  CROSS JOIN LATERAL jsonb_array_elements(op.source_refs) AS ref
  JOIN raw_payload rp
    ON rp.source_name = ref->>'source_name'
   AND rp.source_record_id = ref->>'source_record_id'
  CROSS JOIN LATERAL (
    VALUES
      (
        'phone',
        COALESCE(
          rp.raw_json->'tags'->>'contact:phone',
          rp.raw_json->'tags'->>'phone',
          rp.raw_json->>'businessphone',
          rp.raw_json->>'business_phone',
          rp.raw_json->>'contactphone',
          rp.raw_json->>'contact_phone',
          rp.raw_json->>'phone',
          rp.raw_json->>'phone_number',
          rp.raw_json->>'phonenumber',
          rp.raw_json->>'telephone'
        ),
        NULL::text
      ),
      (
        'email',
        COALESCE(
          rp.raw_json->'tags'->>'contact:email',
          rp.raw_json->'tags'->>'email',
          rp.raw_json->>'businessemail',
          rp.raw_json->>'business_email',
          rp.raw_json->>'contactemail',
          rp.raw_json->>'contact_email',
          rp.raw_json->>'email'
        ),
        NULL::text
      ),
      (
        'website',
        COALESCE(
          rp.raw_json->'tags'->>'contact:website',
          rp.raw_json->'tags'->>'website',
          rp.raw_json->>'businesswebsite',
          rp.raw_json->>'business_website',
          rp.raw_json->>'website',
          rp.raw_json->>'websiteurl',
          rp.raw_json->>'website_url',
          rp.raw_json->>'webaddress',
          rp.raw_json->>'web_address',
          rp.raw_json->>'businessurl',
          rp.raw_json->>'business_url',
          rp.raw_json->>'url'
        ),
        NULL::text
      ),
      (
        'social',
        rp.raw_json->'tags'->>'contact:instagram',
        'instagram'
      ),
      (
        'social',
        rp.raw_json->'tags'->>'contact:facebook',
        'facebook'
      )
  ) AS contact(contact_type, raw_value, platform)
  WHERE ref->>'source_name' IN ('osm_overpass', 'city_vancouver_business_licences')
    AND NULLIF(trim(contact.raw_value), '') IS NOT NULL
),
contact_values AS (
  SELECT * FROM operator_field_values
  UNION ALL
  SELECT * FROM raw_payload_values
),
display_values AS (
  SELECT
    operator_id,
    contact_type,
    platform,
    source_ref,
    confidence_score,
    CASE
      WHEN contact_type = 'email' THEN lower(trim(raw_value))
      WHEN contact_type = 'phone' THEN regexp_replace(trim(raw_value), '\s+', ' ', 'g')
      WHEN contact_type = 'website' THEN
        CASE
          WHEN trim(raw_value) ~* '^//' THEN 'https:' || trim(raw_value)
          WHEN trim(raw_value) ~* '^[a-z][a-z0-9+.-]*://' THEN trim(raw_value)
          ELSE 'https://' || trim(raw_value)
        END
      WHEN contact_type = 'social' AND platform = 'instagram'
        AND trim(raw_value) !~* '^(https?://|www\.)'
        THEN 'https://www.instagram.com/' || regexp_replace(trim(raw_value), '^@+', '')
      WHEN contact_type = 'social' AND platform = 'facebook'
        AND trim(raw_value) !~* '^(https?://|www\.)'
        THEN 'https://www.facebook.com/' || regexp_replace(trim(raw_value), '^@+', '')
      ELSE trim(raw_value)
    END AS value
  FROM contact_values
  WHERE source_ref ? 'source_name'
),
normalized_values AS (
  SELECT
    operator_id,
    contact_type,
    value,
    CASE
      WHEN contact_type = 'phone' THEN regexp_replace(value, '[^0-9+]+', '', 'g')
      WHEN contact_type = 'email' THEN lower(value)
      WHEN contact_type IN ('website', 'social') THEN lower(
        regexp_replace(
          regexp_replace(
            regexp_replace(value, '^[a-z][a-z0-9+.-]*://', '', 'i'),
            '^www\.',
            '',
            'i'
          ),
          '/+$',
          ''
        )
      )
      ELSE lower(value)
    END AS normalized_value,
    platform,
    source_ref,
    confidence_score
  FROM display_values
)
INSERT INTO operator_contact (
  id,
  operator_id,
  contact_type,
  value,
  normalized_value,
  platform,
  source_ref,
  confidence_score
)
SELECT
  'contact_backfill_' || substr(
    md5(
      operator_id || '|' || contact_type || '|' || normalized_value || '|' ||
      COALESCE(platform, '')
    ),
    1,
    32
  ) AS id,
  operator_id,
  contact_type,
  value,
  normalized_value,
  NULLIF(platform, '') AS platform,
  source_ref,
  confidence_score
FROM normalized_values
WHERE contact_type IN ('phone', 'email', 'website', 'social')
  AND NULLIF(value, '') IS NOT NULL
  AND NULLIF(normalized_value, '') IS NOT NULL
  AND (
    (contact_type = 'phone' AND length(regexp_replace(value, '\D+', '', 'g')) >= 7)
    OR (contact_type = 'email' AND value ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$')
    OR (contact_type IN ('website', 'social') AND normalized_value LIKE '%.%')
  )
ON CONFLICT DO NOTHING;
