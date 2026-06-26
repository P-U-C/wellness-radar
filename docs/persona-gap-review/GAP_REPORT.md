# Wellness Radar — 11-Persona Live-App Gap Review

**Date:** 2026-06-26
**Method:** 11 independent founder-agents, each a *different operator type*, each driving the **live API** (`http://127.0.0.1:8000`, same data as https://radar.permanentupperclass.com) through the product's 5 headline questions. Every claim below is grounded in a real API response the agent cited; no findings are hypothetical. Full per-persona reports in [`USER_STORIES.md`](./USER_STORIES.md).

**The personas:** (1) Cold plunge & contrast therapy · (2) Boutique strength & conditioning · (3) Longevity / IV / biohacking · (4) Infrared sauna & thermal · (5) Yoga & Pilates · (6) Athlete recovery & mobility · (7) Med-spa / aesthetics · (8) Mobile / at-home massage · (9) Corporate / workplace wellness (B2B) · (10) Women's health & postnatal · (11) Social wellness club (blended concept).

---

## The one-line finding

**Wellness Radar is a trustworthy, genuinely useful product for exactly one category — recovery / contrast therapy (the wedge) — and structurally thin-to-blind for the other ten operator types. It is a deep vertical slice presented as a horizontal product.**

The two founders whose business *is* the wedge (cold plunge, athlete recovery) got real, actionable, verifiable answers: ranked where-to-open neighborhoods, named competitors, catchment math. The other nine walked away saying "it can't see my business." The engine clearly works — every gap below is a coverage, data, or taxonomy gap, **not** a broken engine. That is the encouraging part: this is a fill-in problem, not a rebuild.

---

## What's genuinely good (preserve at all costs)

Praised by nearly every persona, including the skeptics:

- **Source provenance & auditability.** Every operator, proposition, signal, and score carries `source_refs` with URL, licence, `trust_tier`, and `seen_at`. Multiple founders called this *better than paid tools*. "When the app speaks, it shows its work."
- **Radical honesty.** `is_stub: true` on fixtures, explicit `confidence_score` (0.40–0.46, not oversold), `/admin/source-freshness` flagging `bc_data_catalogue` stale, and a published `/analytics/methodology` with the exact formulas and the caveat "white-space is a signal, not guaranteed economic attractiveness." Founders trusted the tool *because* it admits what it doesn't know.
- **Real, verifiable supply census.** 1,969 geocoded, source-backed operators across 15 municipalities. Spot-checked competitors came back "open" with live websites.
- **The recovery wedge works end-to-end.** Whitespace → ranked neighborhoods (Vancouver 0.8997, Richmond/Surrey zero-supply), propositions with $543M catchment math and named competitors, verifiable competitor map (Tality's 3 locations, Kolm Kontrast, Regen). For this category it's a real decision aid.
- **`/analytics/category-velocity` is strong where populated** (e.g. `fitness_movement` 221 new ops/30d, `allied_health` 148/30d — sourced to dated licence records).

---

## Consolidated gaps, ranked (persona-hit-count × severity)

### Tier 1 — Universal. Hit by nearly everyone. Fix first.

**G1 · Worldwide-trend match (Q4) + first-mover cities (Q5) are 100% fixture / null — 2 of the 5 headline questions are non-functional product-wide.** — **11/11 · High**
`/trends` is entirely `is_stub: true`, `source: peer_city_trends_fixture`, whose own methodology says values "must be replaced by a reviewed Trends provider before any claim of live search demand." On bundles, `worldwide_match: null` and `first_mover_cities: []` for everything outside recovery. Every founder wanted "is this a global wave or a local blip" and "what did Austin/NYC do 18mo ago" — and every founder got placeholder data or empty arrays. *Even covered categories only get a normalized 0–100 curve with no "what they actually did" playbook.*

**G2 · Leads aren't actionable — the "who do I call" layer is mostly empty.** — **10/11 · High**
`/operators` meta: `with_contact_count 251/1969 = 12.75%`. Real category competitors carry no phone (Tality, Kolm Kontrast, Regen all `phone: false`). `/leads` returns gyms/yoga regardless of the founder's category; category competitors are absent. `/leads/{id}` **404s** (longevity persona). For solo founders this was repeatedly named the single most valuable missing thing: "It nails *who exists* and completely whiffs *who I can actually talk to*."

**G3 · `/people` & people-graph can't surface category leaders.** — **11/11 · Med**
`/people` is led by Dr. Bonnie Henry and provincial politicians (`primary_category: null`); `/people-graph` returns 750 nodes with category `NONE`. The only category "people" are org placeholders like `person_aetherhaus_team` (`contactable: false, contacts: []`). "Who's driving it" (Q3) returns government officials for everyone.

**G4 · Whitespace + opportunity-scorecards are computed ONLY for `recovery_contrast_therapy` — no "where to open" answer for any other category.** — **9/11 · High**
`/analytics/whitespace` (14 rows) and `/analytics/opportunity-scorecards` (10 rows) are 100% recovery. The flagship per-neighborhood supply-vs-demand decision tool — the core "where" answer — was never run for boutique strength, yoga, longevity, spa-thermal, allied-health, aesthetics, women's-health, or social. Nine founders had to fall back to raw `/propositions` or hand-tally `/operators`.

**G5 · Categorization is too loose to trust — mis-clustered bundles pollute every supply count and competitor read.** — **8/11 · High**
Documented misfilings: bouldering crags ("Cougar Crag", "Tombstone Tower") and indoor golf in **Longevity / IV**; drug-rehab nonprofits ("Together We Can") in **Cold plunge**; a martial-arts licence in **Boutique strength**; nail salons, counselling, and "THIRD SPACE CONTRACTING LTD" (a contractor) in **Spa & thermal**; nail spas + physio in **Social wellness**; pilates/yoga/barre folded into **fitness** competitor counts. Every downstream supply-density and competitor number inherits this noise.

**G6 · Demand is one flat per-capita recreation-spend proxy — no demographic, income, medical, or employer dimension.** — **8/11 · High**
Every proposition sizes demand as `population × $2,180 StatCan recreation spend`, self-labeled "context for demand, not capturable revenue." A young-family block and a retiree block score identically. Spa/thermal is sized on *hair-grooming* spend ($215). No income/affluence for high-ticket clinics, no birth-rate/age-band for demographic niches, no firmographic data for B2B. `target_demo_fit` exists (0.15 weight) but is an opaque, un-tunable category-level scalar.

### Tier 2 — Correctness bugs that actively break trust.

**G7 · Neighborhood geo / denominator bug — populations and even cities are wrong.** — **5/11 · High**
CSD-percentage allocation produces `Downtown = 248,343` ("37.5% of Vancouver"; reality ~62k) and `Marpole = "100.0% share of Richmond, 209,937"` (Marpole is in *Vancouver*). Every per-neighborhood market size is a city-wide proxy in disguise, and at least one top-ranked pick is attributed to the wrong municipality.

**G8 · Scoring gives false green lights on saturated categories.** — **4/11 · High**
`bundle_yoga_pilates` scores `low_supply_density 0.947` / `demand_proxy 0.9912` (3rd of 10) — i.e. the model calls mature, overbuilt yoga/Pilates *under-supplied and high-demand*. The yoga founder came specifically to have her optimism corrected and got the opposite. Compounded by **G11** duplication. Separately, the same category can rank **last** in `/bundles` (cold plunge 0.6545) and **first** in `/analytics/whitespace` (0.8997) with no reconciliation — the two headline scores point in opposite directions.

**G9 · Propositions route founders *into* competitor-dense blocks and skip the true zero-supply markets.** — **4/11 · High**
The recovery whitespace engine ranks Richmond/Surrey (0 supply) top, but the generated proposition *cards* cover Edmonds/Fairview/Mount Pleasant — and Fairview/Mount Pleasant carry 9 competitors. The top fitness card headlines "Downtown whitespace" (0.7465) while its own `nearest_competitors` lists 13 rivals within 4 km. The verdict contradicts the evidence in its own fine print.

**G10 · `/analytics/category-velocity` / momentum returns null for many categories (inconsistent).** — **5/11 · Med**
Works and is excellent for `fitness_movement`/`allied_health`; returns empty `{}` or `velocity: null` for `spa_thermal`, `nutrition_longevity`, `womens_health`, and the social/aesthetics categories. So the "is it accelerating?" question works for some categories and silently fails for others.

**G11 · Operator duplication + null geo corrupt supply counts.** — **3/11 · Med**
Oxygen Yoga appears **11×**, Club Pilates **7×**, Lagree West 3× in `/operators`. ~40% of fitness operators have `municipality: null` and ~31 `neighborhood: null`. Density, supply, and "underserved municipality" reads are unreliable until dedupe + geo-backfill.

### Tier 3 — The model can't represent whole classes of business ("blind to my category").

**G12 · Missing taxonomies — entire operator classes are invisible.** — **5/11 · High**
Name-search across all 1,969 operators returned **0** for: botox/injectable/skin/filler/cosmetic/lymphatic (med-spa); prenatal/postnatal/pelvic/lactation/doula/midwife (women's health); cafe/coworking/sober (social club); cryo/normatec/compression/percussion/mobility (athlete recovery); reformer (Pilates). The taxonomy is 16 sport/service categories; aesthetics, women's-health, hospitality, and recovery-modality classes simply don't exist. The few real operators that exist (QUEST Medical Aesthetics, Cedar Pregnancy Care) are **misfiled** into fitness/allied-health and never surface.

**G13 · Place-pin-only model — no mobile/service-area, co-location, blended-concept, or employer object.** — **4/11 · High**
- *Mobile massage:* every operator is a fixed pin; no `is_mobile` / `service_area` field; all demand math is "competitors within 4 km of an address" — useless to a route-based business.
- *Athlete recovery:* no proximity/co-location scoring (can't ask "recovery whitespace next to a performance gym"), no partnership/team leads.
- *Corporate B2B:* no firmographic/employer object at all (`/admin/exports/firmographics|employers|organizations` all rejected); `job_velocity_count` = 0 for every category; demand is consumer household spend.
- *Social club:* a blended concept gets shredded into a single `community_social_wellness` tag; the cafe/coworking/sober pillars vanish.

**G14 · No medical / regulated vs fitness distinction.** — **2/11 · High (for those types)**
The app tagged "QUEST MEDICAL AESTHETICS" as a "Municipal recreation facility" (`venue_class: unknown`). There is no College-of-Physicians / health-authority / regulated flag — the exact distinction a medical-adjacent clinic lives on.

**G15 · Operator filters ignored / not text-searchable by category.** — **3/11 · Med**
`/operators?neighborhood=Downtown` returned operators in Kensington-Cedar Cottage and Victoria-Fraserview (filter silently ignored). Category lives in a `categories` array not exposed to text search, so founders can't slice the competitor map by area or keyword.

---

## Recommended fix roadmap (prioritized)

**P0 — Make the product trustworthy for its own wedge, and honest elsewhere.** *(Correctness; small, high-leverage.)*
1. Fix the geo/denominator bug (G7) — neighborhood populations must come from the neighborhood, not a CSD %-share, and must not cross municipality lines.
2. Dedupe operators (G11), then add a **saturation / over-supply signal** so crowded categories score *red* (G8); reconcile or merge the bundle-score vs whitespace-score so they can't point opposite directions.
3. Category-hygiene pass (G5/G12 misfiling) — evict crags, rehab nonprofits, nail salons, and contractors from wellness bundles; reclassify the real med-spa/women's-health operators you already have.
4. Either ship a real Trends provider or **gate Q4/Q5 as "coming soon"** instead of rendering fake `breakout` (G1) — showing fixtures as if they were demand is the biggest trust risk.

**P1 — Extend the working engine to the other ten categories.**
5. Run `/analytics/whitespace` + `/opportunity-scorecards` for **all** bundles, not just recovery (G4).
6. Make leads actionable (G2): backfill contacts, fix `/leads/{id}` 404, surface each category's real competitors as contactable leads.
7. Fix `category-velocity` null categories (G10); make `/people` segmentable by category and demote policy figures (G3).

**P2 — Broaden the model beyond place + single-category.**
8. Add a **demographic layer** (census age-band / household-with-children / income by neighborhood) into the demand proxy, and expose `target_demo_fit` as a tunable filter (G6).
9. Add missing **taxonomies** (aesthetics/med-spa, women's-health, sober-social/cafe/coworking, recovery-modalities) + a **medical/regulated flag** (G12/G14).
10. Support **non-storefront models** (G13): `is_mobile`/service-area operators, co-location/proximity scoring, a firmographic/employer object for B2B, and blended-concept tagging.

---

## How to read this against the product's intent

The radar was built around 5 questions. Scored against them by 11 real operator types on live data:

| Question | Recovery wedge (2 personas) | Other 9 operator types |
|---|---|---|
| Q1 What's available | ✅ real, verifiable | ⚠️ census exists but mis-categorized / business invisible |
| Q2 Bundle + score | ✅ works | ⚠️ bundle exists but mislabeled; false green lights |
| Q3 Who's driving it | ⚠️ org placeholders, no contacts | ❌ government officials, uncontactable |
| Q4 Worldwide trend | ❌ fixture | ❌ fixture / absent |
| Q5 First-mover cities | ❌ fixture/empty | ❌ empty |
| "Where to open" (whitespace) | ✅ genuinely useful | ❌ not computed for the category |
| "Who to contact" (leads) | ⚠️ 2 float-tank leads | ❌ wrong-category / no contacts |

The wedge is real. The horizontal product is mostly the wedge's machinery waiting to be pointed at the other categories — plus three correctness bugs (geo, dedupe/saturation, categorization) that should be fixed before any of it is trusted.
