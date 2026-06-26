# Vancouver Wellness Radar — Data Source Expansion Report

*Scope: Metro Vancouver / BC wellness market-intelligence console. Every source below is assessed against the four hard constraints (BC geo-gate, rights/ToS, provenance/trust-tier, real working endpoint) and the pipeline: source → raw_payload → normalize → bc_gate → canonical table → source_event → signal → API → UI.*

## TL;DR
- **The biggest gap (demand-side signals) has NO single clean free source.** The realistic build is a hybrid: the official Google Trends API (2025 alpha, invite-only, BC/province-level only) plus Yelp Fusion (Places) for reviews/ratings/price-tier, with paid foot-traffic (Placer.ai, enterprise quote) only if funded. Replace the placeholder trend with Google Trends (apply now) bridged by SerpApi in the interim.
- **Ownership, missing-municipality, and permit gaps are fully fillable TODAY** with clean, OGL-licensed government sources: OrgBook BC API, per-municipality ArcGIS hubs (Richmond, Coquitlam, New West, Delta, Langley, Surrey, Burnaby, North Van), Metro Vancouver regional, Vancouver building permits, and StatCan business counts.
- **Real estate/lease and BC Assessment data are NOT free** — flag as paid/licensed (BC Assessment Data Advice, Spacelist, REALTOR.ca DDF). There is no free commercial-lease feed for Metro Vancouver.

## Key Findings (trust tiers + pipeline-readiness)
All BC government open data rides the **Open Government Licence – British Columbia** (worldwide, royalty-free, perpetual, commercial use permitted, attribution required: "Contains information licensed under the Open Government Licence – British Columbia") — clearly open, **official** tier. Municipal ArcGIS Hub portals expose GeoServices/REST/GeoJSON/CSV/WMS/WFS endpoints in a uniform pattern, so one ArcGIS connector covers most cities — pipeline-ready. The demand-side and contact gaps are where the **commercial_api** and **legal-review-needed** sources cluster, and where caching restrictions directly threaten the canonical-table persistence model.

---

## GAP 1 — Demand-Side Signals (THE BIGGEST GAP: search interest, reviews, foot traffic)

### Google Trends API (OFFICIAL, 2025 alpha) — replaces the placeholder trend
- **Data:** Search interest over time, region/subregion breakdowns (ISO 3166-2), rolling 1,800-day (~5yr) window, data to ~48h ago, daily/weekly/monthly/yearly aggregation, consistently-scaled values (not the website's 0–100).
- **Gap filled:** Demand-side search interest (the fixture/placeholder replacement).
- **URL (VERIFIED):** docs/signup https://developers.google.com/search/apis/trends ; announcement (July 24, 2025) https://developers.google.com/search/blog/2025/07/trends-api
- **Geo-fit:** Officially confirmed only to ISO 3166-2 sub-region level = province (**CA-BC**). City/metro granularity is claimed by SEO blogs but is **NOT** confirmed in Google's official text — treat cautiously. bc_gate = filter to CA-BC.
- **Rights/ToS:** Uses Google Cloud credentials; documentation page licensed CC BY 4.0. **Pricing is not published — do NOT assume free.** Legal-review-needed.
- **Trust tier:** commercial_api (official Google source, but produces inferred-interest signals).
- **Cadence:** ~48h lag; daily/weekly/monthly. **Effort:** Med (access requires alpha-tester application approval; rolling rollout). **Confidence:** URLs VERIFIED; access INFERRED (invite-only alpha, not GA).

### SerpApi Google Trends (commercial bridge / interim)
- **Data:** Programmatic Google Trends results, geo filter, up to 5 queries per search.
- **URL (VERIFIED):** https://serpapi.com/google-trends-api (endpoint `https://serpapi.com/search?engine=google_trends`)
- **Geo-fit:** `geo` param → filter to BC.
- **Rights:** Paid. Developer **$75/mo (5,000 searches)**; Production **$150/mo (15,000 searches)**. SerpApi's **"U.S. Legal Shield"** is *"Included with the Production Plan and above, with up to $2 million in coverage,"* and *"covers the scraping and parsing of search engine data, as long as your use of the data or service is not illegal."* Note the Developer tier lacks the Shield. Legal-review-needed.
- **Trust tier:** commercial_api. **Cadence:** on-demand. **Effort:** Low. **Confidence:** VERIFIED.

### Yelp Fusion (Places) API — best clean demand + pricing proxy
- **Data:** Ratings, review counts, price tier ($–$$$$), categories, coordinates, hours; first 160 chars of review excerpts (3 on Plus, 7 on Enterprise).
- **Gap filled:** Demand-side reviews/ratings AND pricing/positioning (Gaps 1 & 4).
- **URL (VERIFIED):** `https://api.yelp.com/v3/businesses/search` ; docs https://docs.developer.yelp.com/
- **Geo-fit:** `location`/lat-long params → filter to Metro Vancouver.
- **Rights:** 30-day free trial (5,000 calls). Paid tiers are **per-1,000-calls: Starter $7.99/1k, Plus $9.99/1k, Enterprise $14.99/1k**; sales contact required above 150,000 monthly calls. **CRITICAL ToS** (API Terms of Use, last updated January 13, 2025, verbatim): *"you will not… cache, record, pre-fetch, or otherwise store any portion of the Yelp Content for a period longer than twenty-four (24) hours from receipt… with the exception of… storing Yelp business IDs which you may use solely for back-end matching purposes."* Places = consumer-facing display rights; Insights = B2B internal-only, no display rights. ToS https://terms.yelp.com/developers/api_terms/ — **legal-review-needed**: the 24h rule means only Yelp business IDs may persist in the canonical table; ratings/review content must be refreshed, not stored.
- **Trust tier:** commercial_api. **Cadence:** real-time. **Effort:** Med (caching constraint). **Confidence:** VERIFIED.

### Google Places API
- **Data:** POI details, ratings, price level, hours, atmosphere (user-content) fields.
- **URL (VERIFIED):** https://developers.google.com/maps/documentation/places/web-service ; policies https://developers.google.com/maps/documentation/places/web-service/policies
- **Rights:** Pay-as-you-go SKUs with a $200/mo credit. **HARD ToS:** cannot pre-fetch/cache/store content beyond allowed exceptions (effectively ~30 days), **EXCEPT `place_id`, which is exempt and storable indefinitely**; results shown on a map must be on a Google Map, with Google attribution. Legal-review-needed.
- **Trust tier:** commercial_api. **Cadence:** real-time. **Effort:** Med. **Confidence:** VERIFIED. **Note:** store only `place_id` in the canonical table; everything else is a transient signal.

### Paid foot-traffic providers (NO clean free source)
- **Placer.ai** — does **NOT** publish pricing (custom enterprise quotes only). Sourced third-party benchmarks vary widely: Software Finder (2026) estimates *"between $5,000 and $30,000/year, based on industry benchmarks,"* while a Tontitown vendor comparison lists *"~$12K–$50K+/yr (enterprise tiers)."* Treat any single figure as an unconfirmed top-of-range estimate. Has an API (https://www.placer.ai/products/api). US-centric; **Canadian coverage must be confirmed** before committing.
- **SafeGraph (now part of Dewey), Unacast, Foursquare** — POI + visit/mobility data; marketplace/custom pricing. SafeGraph offers free POI samples and open census datasets.
- **Trust tier:** commercial_api. **Effort:** High. **Confidence:** pricing ranges sourced but not vendor-confirmed; Canada coverage INFERRED.
- **Honest call:** Foot-traffic for Metro Van wellness operators has no free option and uncertain Canadian granularity. Partnership/paid only — **defer unless funded.**

### Reddit (community signals)
- **Data:** Community posts/sentiment (r/vancouver, r/saunas, recovery/cold-plunge threads).
- **Rights:** Per Reddit's **Responsible Builder Policy (updated November 11, 2025)**, the limit is *"100 queries per minute (QPM) per OAuth client ID, averaged over a 10-minute window,"* and the policy *"applies to everyone—whether you're a developer, moderator, researcher, or a bot—and requires explicit approval before accessing any Reddit data."* Commercial use needs approval; AI/ML training on Reddit data is prohibited without consent. Legal-review-needed.
- **Trust tier:** community (lower trust). **Effort:** Med-High (pre-approval). **Confidence:** VERIFIED. Public subreddit RSS (e.g., `https://www.reddit.com/r/vancouver/.rss`) is a lighter **informal**-tier option but limited in depth.

---

## GAP 2 — Decision-Maker / Ownership Data

### OrgBook BC API (TOP PICK)
- **Data:** Every legally registered BC organization — legal name, "Doing Business As" names, registration number, CRA business number, entity type/status, related orgs. Sourced as verifiable credentials from BC Registries.
- **Gap filled:** Who owns/runs the businesses (entity-level ownership and DBA resolution).
- **URL (VERIFIED):** https://orgbook.gov.bc.ca ; API docs https://bcgov.github.io/orgbook-bc-api-docs/ ; production v4 REST endpoints e.g. `/v4/search/autocomplete`, `/v4/search/topic`, topic detail by `source_id` (BC company number).
- **Geo-fit:** BC-only by definition (1.4M+ active entities). bc_gate is intrinsic.
- **Rights:** Open, OGL-BC; **no API key needed** for public data. Clearly open.
- **Trust tier:** official. **Cadence:** updated within minutes of a registration change. **Effort:** Low-Med. **Confidence:** VERIFIED.
- **Important limit:** Provides registered entity + DBA + business number, **NOT** individual directors/officers. Personal director data sits behind paid BC Registries document orders and is private — do not scrape. For human decision-makers, OrgBook gives the legal entity; pair with **manual/AI-inferred operator seeds** (existing) for named contacts.

### Municipal business-licence datasets (ownership proxy)
Most municipal licence datasets carry the business/operator name, which you can join to OrgBook on name/number to confirm the legal entity. Endpoints listed under Gap 5.

---

## GAP 3 — Real Estate / Lease / Zoning

### Municipal zoning ArcGIS layers (FREE, clearly open)
- **Vancouver zoning districts & labels:** https://opendata.vancouver.ca/explore/dataset/zoning-districts-and-labels/ — weekly refresh, OGL-Vancouver. VERIFIED.
- **Richmond zoning districts:** https://richmond-geo-hub-cor.hub.arcgis.com/datasets/zoning-districts-1 — VERIFIED.
- Other municipalities expose equivalent zoning FeatureServers via their ArcGIS hubs.
- **Trust tier:** official. **Effort:** Low. **Geo-fit:** BC-specific.

### BC Assessment (PAID — flag)
- **Data:** Assessed values, folio, land/improvement split, three most-recent sales, property class — the canonical property/valuation layer.
- **Rights:** **NOT free for commercial use.** "Data Advice" product is licensed via BC Assessment's Data Partnerships Team (propertyinfo@bcassessment.ca; 1-866-825-8322) under a Commercial Data Licensing Agreement. Academic access exists via Abacus but is restricted to SFU/UBC/UNBC/UVic. The public bcassessment.ca site explicitly prohibits commercial use "except with the prior written authority of the owner of the copyright."
- **Trust tier:** official (paid/licensed). **Effort:** High (licensing + contract). **Confidence:** VERIFIED paid.

### Commercial lease listings (PAID / licensed / ToS-risk)
- **Spacelist** (spacelist.ca) — Canadian commercial RE marketplace; offers API endpoints + scheduled CSV reports (info.spacelist.co/data). Licensed/paid — cleanest paid route for lease availability.
- **REALTOR.ca DDF** (ddfapi-docs.realtor.ca) — per Repliers, *"the REALTOR.ca DDF® typically includes about 60-65% of the active listings across the country… Notably, Saskatchewan and Quebec are excluded from this feed."* Residential-skewed; requires a data-distribution agreement.
- **Apify Realtor.ca scrapers** (~$0.5/1K) — scraping route, **ToS-risk / legal-review-needed**.
- **Trust tier:** commercial_api. **Effort:** Med-High. **Confidence:** VERIFIED.
- **Honest call:** No free commercial-lease feed for Metro Vancouver. A **Spacelist partnership** is the cleanest paid route for lease availability.

---

## GAP 4 — Pricing / Positioning
No dedicated open pricing feed exists for wellness services. Best available, in order of cleanliness:
- **Yelp price tier** ($–$$$$) and **Google Places price level** (see Gap 1) — commercial_api, subject to caching limits.
- **Manual / AI-inferred** pricing scrapes from operator booking pages and platforms (Mindbody, Janeapp, etc.) → **ai_inferred** trust tier. These platforms carry restrictive ToS — **legal-review-needed** before automated collection. For a recovery/sauna/cold-plunge wedge, a small **manually-seeded pricing table** (informal/manual tier) is the pragmatic, rights-clean starting point.

---

## GAP 5 — Missing Municipalities (regional + per-city)

### Metro Vancouver Open Data Portal (regional)
- **URL (VERIFIED):** https://open-data-portal-metrovancouver.hub.arcgis.com/ — ArcGIS Hub; CSV/KML/GeoJSON + GeoServices/WMS/WFS. Regional land use, facilities, planning. Released under Metro Vancouver's Open Government Licence ("freely used, re-used and redistributed for any lawful purpose").
- **Trust tier:** official. **Effort:** Low.

### Per-municipality (all ArcGIS Hub / REST — clearly open, OGL-municipal except where noted)
- **Richmond GeoHub** (parcels, zoning, interactive map): https://richmond-geo-hub-cor.hub.arcgis.com/ — VERIFIED.
- **Coquitlam Business Licences:** https://hub.arcgis.com/maps/Coquitlam::coquitlam-business-licences/about — VERIFIED.
- **New Westminster Business Licenses (All):** https://opendata.newwestcity.ca/datasets/05550b73a3b847e7abe127ebd8cf0327 — 3,817 records; **"Custom License" — verify reuse terms before integrating.** VERIFIED.
- **Township of Langley Business Licenses:** https://data-tol.opendata.arcgis.com/datasets/TOL::business-licenses/about — VERIFIED.
- **Delta Open Data:** https://opendata-deltabc.hub.arcgis.com/ — VERIFIED.
- **District of North Vancouver GEOweb:** https://geoweb.dnv.org/data/ — products refreshed weekly via automated routines. VERIFIED.
- **Surrey Business Licences:** https://data.surrey.ca/dataset/business-licences — annual (tables created at start of each year), **Open Government Licence – City of Surrey.** VERIFIED.
- **Surrey Building Permits:** https://data.surrey.ca/dataset/building-permits — monthly summaries, updated within days, OGL-Surrey. VERIFIED. (Surrey API hub: https://opendata-surrey.hub.arcgis.com/)
- **Burnaby Business Licences:** https://data.burnaby.ca/datasets/burnaby::business-licences/about — ArcGIS Feature Service (CSV/GeoJSON/KML/Shapefile). VERIFIED loads; **update cadence and exact license text not confirmed — verify on dataset's about/API tab.**
- **Geo-fit:** all BC-specific; bc_gate passes trivially. **Trust tier:** official. **Effort:** Low — one ArcGIS REST connector handles the common pattern; per-city field mapping is the main work.

### Statistics Canada — Canadian Business Counts by CSD + NAICS
- **Data:** Active business counts by 6-digit NAICS and employment-size band, by census subdivision / CMA (semi-annual). The market-sizing denominator for wellness NAICS codes.
- **URL (VERIFIED):** latest Table **33-10-1097-01** (reference period December 2025; **release date 2026-02-13**) https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3310109701 ; bulk CSV https://www150.statcan.gc.ca/n1/tbl/csv/33101097-eng.zip . Context from The Daily (Feb 13, 2026): *"In December, there were 1.37 million employer businesses in Canada and 3.67 million non-employer businesses with annual revenues greater than $30,000."*
- **Geo-fit:** filter to BC CSDs / Vancouver CMA. **Rights:** Statistics Canada Open Licence. Clearly open. **Trust tier:** official. **Cadence:** semi-annual. **Effort:** Low. **Confidence:** VERIFIED.

---

## GAP 6 — Permits / Development Applications (supply-pipeline leading indicator)

### City of Vancouver Issued Building Permits
- **Data:** All permits since 2017 — PropertyUse, TypeofWork, SpecificUseCategory, PermitCategory, elapsed days. Current-year extract updated **daily**; prior years static.
- **URL (VERIFIED):** https://opendata.vancouver.ca/explore/dataset/issued-building-permits/ ; API v2.1 console https://opendata.vancouver.ca/api/explore/v2.1/console
- **Geo-fit:** Vancouver. **Rights:** Open Government Licence – Vancouver. Clearly open. **Trust tier:** official. **Effort:** Low. **Confidence:** VERIFIED.
- **Companions:** Vancouver active/archived rezoning + development-permit application datasets on the same portal (supply pipeline upstream of permits).

### BC Stats Building Permits (BPER) — provincial
- **Data:** Permit values + residential units created, at census-division and census-subdivision level, 2003–present (methodology break at Jan 2018).
- **URL (VERIFIED):** https://catalogue.data.gov.bc.ca/dataset/45a00be0-d572-4e42-be18-1bbaaf6c85ee ; monthly XLSX/CSV resources.
- **Geo-fit:** filter to BC CSDs. **Rights:** OGL-BC. Clearly open. **Trust tier:** official. **Effort:** Low. **Confidence:** VERIFIED.

### Surrey Building Permits — see Gap 5. Other municipal permit datasets are discoverable on each city's ArcGIS hub.

### BC Data Catalogue (CKAN) — master discovery layer
- **URL (VERIFIED):** `https://catalogue.data.gov.bc.ca/api/3/action/package_search?q=<term>` (e.g., `?q=recreation`, `?q=building+permits`). No API key needed for public OGL-BC data.
- **Use:** programmatic discovery of additional BC datasets (recreation sites/trails, tourism room revenue, etc.) to extend the pipeline. **Trust tier:** official. **Effort:** Low. **Confidence:** VERIFIED.
- **Adjacent demand-context datasets surfaced here:** Recreation Sites & Trails BC (WMS/KML via openmaps.gov.bc.ca), Destination BC / BC Stats tourism room-revenue and the Tourism Industry Dashboard — useful **official** context layers, though tourism data is region-level, not operator-level.

---

## TOP 5 TO BUILD NEXT (ranked by impact × low-effort × rights-clean)

1. **OrgBook BC API** — Fills the ownership gap; BC-only, OGL-open, free, REST, minutes-fresh. Highest impact-per-effort and zero rights risk. *(official)*
2. **Per-municipality ArcGIS business-licence + permit hubs (Richmond, Surrey, Coquitlam, New West, Langley, Delta, Burnaby, North Van) + Metro Vancouver regional** — Closes the missing-municipality gap AND seeds the supply-pipeline gap through a single reusable ArcGIS REST connector. OGL-open (verify New West "Custom License" and Burnaby license). *(official)*
3. **City of Vancouver Issued Building Permits + StatCan Business Counts (33-10-1097-01)** — Supply-pipeline leading indicator (daily) plus the market-sizing denominator (semi-annual). Both open, CSV/API, low effort. *(official)*
4. **Yelp Fusion (Places) API** — The cleanest demand + pricing proxy (ratings, review counts, $–$$$$) for the recovery/sauna/cold-plunge wedge. Free trial → ~$8–15/1k calls; architect for the 24h cache rule (persist only Yelp business IDs). *(commercial_api)*
5. **Google Trends API (official alpha) — apply now; SerpApi Google Trends as the interim bridge** — Replaces the placeholder trend with real BC search-interest signal. Apply for alpha access immediately; run SerpApi (~$75/mo) as a verified bridge until granted. BC/province-level geo only. *(commercial_api)*

## Recommendations (staged)
- **Stage 1 (build this sprint, zero rights risk):** OrgBook BC + the ArcGIS municipal connector + Vancouver/Surrey permits + StatCan counts. This alone closes Gaps 2, 5, and 6 and upgrades the people graph and opportunity analytics from seeds to live data.
- **Stage 2 (demand-side, with legal review):** Stand up Yelp Fusion (Places) with an ID-only persistence model, and submit the Google Trends alpha application while wiring SerpApi as the interim trend feed. This retires the fixture/placeholder. **Threshold to proceed:** legal sign-off on Yelp's 24h cache rule and Google Places' place_id-only storage.
- **Stage 3 (paid, only if funded / validated):** Evaluate a Spacelist lease-data partnership and a BC Assessment Data Advice licence once the free layers prove product-market fit. **Threshold to proceed:** a paying customer or funded pilot — these are 4–5 figure annual commitments. Foot-traffic (Placer.ai/SafeGraph) only after confirming Metro Vancouver coverage in a trial.
- **Trigger to revisit Google Trends granularity:** if Google's alpha confirms sub-province (city/metro) breakdowns for Canada, elevate it from province-level context to a primary neighborhood-level demand signal.

## Caveats
- **Demand-side foot traffic** (Placer.ai/SafeGraph/Unacast) is paid-only, Placer.ai does not publish pricing (third-party estimates span ~$5k–$50k+/yr), and Canadian granularity is unconfirmed — defer unless funded.
- **Yelp (24h) and Google Places (~30-day; place_id exempt) caching restrictions** directly constrain the canonical-table model. Legal review is required before storing any review/rating content; persist only the stable IDs.
- **BC Assessment and commercial lease feeds are paid/licensed** — no free route. Budget for contracts.
- **Google Trends API is invite-only alpha, not GA;** "free" is unconfirmed (no published pricing), and city/metro-level granularity for Canada is unconfirmed (officially only ISO 3166-2 province = CA-BC).
- **Reddit API now requires pre-approval for all use** (Nov 11, 2025 policy) and prohibits AI/ML training without consent — treat as community/informal, lower trust.
- **New Westminster business-licence dataset shows a "Custom License,"** and **Burnaby's cadence/license were not verified** — confirm reuse terms before integrating both.
- **bc_gate vigilance:** several ArcGIS searches surface *Richmond, Virginia/Texas/California* and *Vancouver, Washington (Clark County)* portals. The bc_gate must reject these — confirm each endpoint resolves to the BC municipality (e.g., richmond.ca / data.surrey.ca / newwestcity.ca), not a US namesake.