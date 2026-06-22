# Opportunity Analytics Methodology

Status: CM5 beta

Opportunity scoring is a source-backed supply-demand signal. It is not a claim that a geography or category is guaranteed to be economically attractive.

## Formula

```text
Opportunity Score =
0.30 demand_proxy
+ 0.20 low_supply_density
+ 0.15 category_growth
+ 0.15 target_demo_fit
+ 0.10 transit_access
+ 0.05 event_community_activity
+ 0.05 source_confidence
```

Every rendered cell and scorecard must include:

- `component_breakdown`
- `source_refs`
- `source_confidence`
- denominator trace IDs
- operator/source-event trace IDs where available

The API filters out rows that do not have the required component values.

## CM5 Inputs

- Supply: PostGIS-backed operator rows by category and CSD/neighborhood. Operators missing source-native neighborhoods are backfilled from reviewed City of Vancouver local-area polygons when point-in-polygon covers the point, then by nearest known neighborhood centroid with `neighborhood_assignment_method = 'nearest_centroid_approximate'`.
- Demand proxy: live Statistics Canada 2021 Census Profile population denominator by CSD, normalized as `log1p(raw_population) / log1p(Vancouver CMA population)` to avoid saturating all large geographies at 1.0.
- Business-count denominator: live Statistics Canada Table 33-10-1016-01 Canadian Business Counts with employees. CM5 uses the current table's available NAICS granularity and stores source vector/coordinate IDs in denominator payloads.
- Target demo fit: average of normalized population demand and same-category business density per 10,000 residents, normalized against observed same-category business density rather than capped at 1.0.
- Category growth: new operators observed in the 180-day window.
- Event/community activity: source-backed signals in the 180-day window, plus event/job tables when populated.
- Transit access: M3 centroid-to-core accessibility proxy derived from stored CSD centroids, not a real transit model.
- Source confidence: average confidence of geography, denominator, operator, and signal inputs.

## Traceability

Tables:

- `statcan_geography`
- `statcan_denominator`
- `opportunity_heatmap_cell`
- `opportunity_scorecard`
- `category_velocity`

Each `opportunity_heatmap_cell.trace_payload` stores denominator IDs, operator IDs, signal counts, raw population, raw business counts, density inputs, demand source status, and neighborhood allocation details where the cell is derived from a parent CSD.

## Limitations After CM5

- Replace centroid-to-core proxy with actual transit-access source data.
- Add reviewed non-Vancouver municipal neighborhood polygons. Current non-Vancouver fallback neighborhoods are labeled approximate and should be treated as lower-confidence grouping aids.
- Add commercial real-estate availability and lease-rate inputs after source-rights review.
- Revisit category-to-NAICS mappings after human review.
