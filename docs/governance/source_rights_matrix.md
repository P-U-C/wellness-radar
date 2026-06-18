# Source Rights Matrix

Status reflects what is encoded in `source_registry.rights_notes` after M4. This is not legal advice. Reviewed rows were checked against official licence pages on 2026-06-18.

| Source | Status | Production note |
|---|---|---|
| `city_vancouver_business_licences` | reviewed | Use with attribution/source links; do not imply City endorsement. |
| `bc_gov_news_rss` | reviewed | Link and excerpt conservatively with BC Government attribution. |
| `health_canada_recalls` | reviewed | Official public recall records; link source and avoid clinical advice. |
| `bc_data_catalogue` | reviewed with data-quality follow-up | Licence is acceptable with attribution; final boundary dataset still needs review. |
| `statcan_wds` | reviewed with data-quality follow-up | Attribution required; table/vector selection remains needs-human-review. |
| `manual_seed` | needs-human-review | Verify each manually curated source page before public launch. |
| `manual_people_csv` | needs-human-review | Verify each public professional source and correction owner before public launch. |
| `osm_overpass` | needs-human-review | Confirm ODbL attribution/share-alike handling for production UI and exports. |
| `orgbook_bc` | needs-human-review | Confirm API terms, retention, and caching policy. |
| `local_rss` | needs-human-review | Per-feed copyright and excerpt policy required. |
| `peer_city_trends_fixture` | needs-human-review | Stub-backed only; do not present as live Google Trends. |
| Disabled backlog sources | needs-human-review | Do not enable until source-specific rights and field allowlists are complete. |

## Field Allowlist Rules

- Persist only public business/operator, official feed, public professional, and public aggregate/statistical fields.
- Do not ingest patient data, private health attributes, LinkedIn-scraped data, private social data, or raw social firehose data.
- Every displayed record must retain `source_refs`.
- Every export must include provenance fields.

## Review References

- City of Vancouver Open Data licence: `https://opendata.vancouver.ca/pages/licence/`
- BC Open Government Licence: `https://www2.gov.bc.ca/gov/content/data/policy-standards/data-policies/open-data/open-government-licence-bc`
- Government of Canada Open Government Licence: `https://open.canada.ca/en/open-government-licence-canada`
- Statistics Canada Open Licence: `https://www.statcan.gc.ca/en/terms-conditions/open-licence`
