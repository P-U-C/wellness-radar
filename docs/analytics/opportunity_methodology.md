# Opportunity Analytics Methodology

Status: M3 beta

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

## M3 Inputs

- Supply: PostGIS-backed operator rows by category and CSD/municipality text match.
- Demand proxy: StatCan population denominator by CSD.
- Business-count denominator: StatCan WDS fixture rows joined through the draft category-to-NAICS crosswalk.
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

Each `opportunity_heatmap_cell.trace_payload` stores denominator IDs, operator IDs, signal counts, and density inputs.

## Limitations for M4

- Replace centroid-to-core proxy with actual transit-access source data.
- Add reviewed neighborhood polygons instead of CSD/municipality grouping.
- Add commercial real-estate availability and lease-rate inputs after source-rights review.
- Revisit category-to-NAICS mappings after human review.
