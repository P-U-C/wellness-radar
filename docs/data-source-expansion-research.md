# Research Prompt — Expand Vancouver Wellness Radar's Data Sources

> Paste this to a research agent (or codex). It is grounded in the radar's real
> current sources and constraints. Goal: find **new, rights-clear data sources**
> that fill the radar's known gaps, each with a concrete access method.

## Context — what the radar is

Vancouver Wellness Radar is a **map-first Metro Vancouver wellness market-
intelligence console** (operator/facility map + signal feed + people graph +
white-space/opportunity analytics). Lead wedge: recovery / contrast therapy /
sauna / cold plunge / social wellness. It is NOT a clinical product.

Every record flows: `source → raw_payload → normalize → bc_gate → canonical
table → source_event → signal → API → UI`. A source is only usable if it can
ride that pipeline.

## Hard constraints (a candidate that violates any of these is out)

1. **Geography:** Metro Vancouver / BC only. Every geo record must pass the
   `bc_gate` (rejects Washington/Clark County/ZIP 98660-98686; accepts BC /
   Vancouver CMA). A US-national or Canada-wide source is fine **only if** it can
   be filtered to BC.
2. **Rights:** public / open-data / licensed for reuse, with a citable terms URL.
   Every source needs a `rights_notes` row. **No LinkedIn scraping. No social
   firehose. No patient-level or private-health data. No private mobility traces.**
3. **Provenance:** every displayed record must carry `source_refs` (source name +
   URL + trust tier). Sources map to a trust tier: `official | reputable_press |
   commercial_api | community | informal | ai_inferred`.
4. **Real endpoint:** must have a concrete access method — REST/JSON API, ArcGIS
   FeatureServer, CSV/GeoJSON download, RSS, or documented open-data portal. "It
   exists somewhere" is not enough; find the actual URL.

## Current sources (DO NOT re-suggest these — they're already in)

| Source | Provides | Tier | Cadence |
|---|---|---|---|
| `city_vancouver_business_licences` | Vancouver wellness/fitness business licences | official | daily |
| `municipal_facilities` (West Van/Surrey/Burnaby ArcGIS) | civic rec facilities | official | weekly |
| `osm_overpass` | OSM-tagged wellness/fitness places + first-mover city counts | community | weekly |
| `statcan_wds` | StatCan census denominators (population) | official | annual |
| `city_vancouver_local_area_boundary` | neighborhood boundaries | official | rarely |
| `peer_city_trends_fixture` | peer-city trend benchmark — **FIXTURE, not live** | informal | manual |
| `manual_seed` / `manual_people_csv` | hand-curated recovery operators / people | informal | manual |

Disabled/stub today: Richmond + North Vancouver municipal facilities (no clean
endpoint found yet); GDELT/WorkBC/health-authority adapters; CRE/lease inputs.

## Known gaps to fill (priority order — from two external reviews)

1. **Demand-side signals** — the single biggest gap. The radar has supply
   (places) + population, but no real *demand*: search interest, foot traffic,
   reviews/ratings volume, booking density. The peer-city trend is a fixture.
   Find a **rights-clear live demand proxy filterable to BC/Metro Van**.
2. **Decision-maker / contact data** — operators have phone/website/social
   columns mostly empty. Find public sources of business contacts, founders,
   ownership (BC corporate registry, OrgBook BC, business-licence contact fields).
3. **Real estate / lease availability** — white-space means nothing without
   "where can I actually open." Find rights-clear commercial-lease / retail-
   vacancy / zoning data for Metro Van.
4. **Pricing / positioning** — membership models, price tiers, service menus.
5. **Coverage completeness** — confirmed open endpoints for the municipalities
   still missing (Richmond, North Van, Coquitlam, New West, Delta, Langley) and
   any region-wide layer (Metro Vancouver Regional District open data).
6. **Permits / pipeline** — building permits, development applications,
   tenant-improvement permits = leading indicator of new wellness supply.

## What to return — for EACH candidate source

A row with:
- **Name** + one-line of what it provides
- **Gap it fills** (one of the 6 above)
- **Access method** — exact: API base URL / ArcGIS service URL / open-data portal
  dataset URL / CSV link. Include an example query if you can.
- **Geographic fit** — is it already BC/Metro-Van, or how to filter to it?
- **Rights / ToS** — licence + the terms URL. Flag anything that needs human
  legal review vs. clearly open.
- **Trust tier** (from the list above)
- **Suggested cadence** (daily/weekly/monthly/annual)
- **Integration effort** — low (CSV/ArcGIS like existing adapters) / medium (new
  API + auth) / high (needs scraping or partnership)
- **Confidence** the endpoint is real & usable (you verified the URL vs. inferred)

Then a short **prioritized shortlist**: the top 5 to build next, ranked by
(impact on the gaps × low effort × rights-clean). Be honest where a gap has **no**
rights-clear public source (e.g. foot traffic, reviews) — saying "no clean source
exists, would need a paid provider (name it) or a partnership" is a valid, useful
answer. Do not pad the list with sources that can't actually ride the pipeline.

## Concrete leads worth checking first (verify before recommending)

- **BC Data Catalogue** (catalogue.data.gov.bc.ca) — provincial open data.
- **Metro Vancouver Open Data** (regional district portal) — region-wide layers.
- **Per-municipality open-data portals** — Richmond, Coquitlam, New West, Delta,
  Langley, North Van District/City ArcGIS Hub sites (the missing municipalities).
- **OrgBook BC / BC Registries** — corporate ownership, registration (contacts).
- **City of Vancouver building/development permits** open dataset (supply
  pipeline leading indicator).
- **Google Trends / Glimpse / SerpApi** — for the demand proxy (note: Google
  Trends has no official API; Glimpse/SerpApi are paid — flag cost).
- **Statistics Canada business counts (CBP)** by CSD/NAICS — supply density by
  area, beyond just population.
