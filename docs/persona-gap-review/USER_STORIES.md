# Wellness Radar — 11 Founder User Stories (live-app sessions, 2026-06-26)

Each founder-agent adopted a distinct operator type and used the **live API** to plan a launch, walking the 5 questions and grounding every claim in a real response. Consolidated analysis: [`GAP_REPORT.md`](./GAP_REPORT.md).

---

## 1. Maya — Cold Plunge & Contrast Therapy Studio
**Profile:** Ex-physiotherapist, ~$180k, one flagship recovery studio. This is the app's advertised "lead wedge," so expectations were high.

**Story:** Started at `/brief`, which on day one pointed her at "Edmonds: recovery & contrast whitespace, no competitors within 4 km, $543M catchment." `/bundles` then gut-punched her — cold plunge scores **0.6545, dead last of 10**. But `/analytics/whitespace` said the opposite: recovery in Vancouver **0.8997, the single strongest signal in the system**, with a clean neighborhood ladder (Richmond/Surrey zero-supply, Downtown saturated → go suburban). `/operators` gave a legible, verifiable competitor map (Tality's 3 locations as her chief rival, Kolm Kontrast, Regen, AetherHaus — all confirmed "open"). Then it fell apart on contacts: `/people` is 5 entries (4 politicians), `/leads` had 2 recovery leads and both were *float-tanks*, and her real rivals carry no phone.

**Top gaps:** (H) no contactable category leads — the #1 miss for a solo founder; (H) bundle score (last) flatly contradicts whitespace (first) for the same category, unreconciled; (H) propositions steer to competitor-dense Fairview/Mount Pleasant and skip the zero-supply Richmond/Surrey the app itself flagged; (M) rehab nonprofits miscategorized as contrast therapy inflate supply; (M) all `/trends` fixtures; (M) competitor-count inconsistency (Edmonds prop says 0, whitespace says 2).

**Verdict:** "Frame my launch, not decide it." Trusts the competitor map and methodology transparency; can't pull the trigger. **Biggest missing thing: contactable category leads** — she needs to call the owner of Art of Sauna about buildout/permitting/drainage, and gets four politicians instead.

---

## 2. Devon — Boutique Strength & Conditioning Gym
**Profile:** Former competitive lifter, one successful Calgary gym, ~$300k for a second location, data-comfortable.

**Story:** `/bundles` has a first-class `bundle_boutique_strength` (189 members, 0.716, #2 of 10) with a transparent formula — but `momentum 0.1085`, so the score is demand + thin supply, not growth. `/analytics/category-velocity` reassured him: `fitness_movement` 221 new ops/30d, the busiest category. `/propositions` named real competitors (Fitness World Granville, Lagree West, Club Pilates) — but the "Downtown" card sizes the market at 248,343 people ("37.5% of Vancouver"; Downtown is ~62k). `top_people` for his bundle = one misclassified martial-arts licence. `worldwide_match: null`, `first_mover_cities: []`, and `/trends` has zero strength terms.

**Top gaps:** (H) Q4/Q5 empty for his category; (H) "who's driving it" effectively missing; (H) Downtown=248k denominator is broken; (H) whitespace/scorecards never computed for fitness; (M) no block-by-block competitor density (addresses are "(none)"); (M) pilates/yoga/barre fold into "fitness" and inflate his competitor count; (M) ~40% of fitness ops have null municipality.

**Verdict:** "Starting filter yes, decision tool no." Trusts the sourcing more than the analytics. **Biggest missing thing: a strength-specific trend/first-mover layer + clean category separation** — the app can't tell him if boutique barbell is a durable wave or if he's just early-and-alone.

---

## 3. Dr. Priya — Longevity / IV / Biohacking Clinic
**Profile:** MD + partner, ~$500k, high-ticket medical-adjacent clinic, needs an affluent catchment.

**Story:** `/bundles` has a "Longevity / IV" bundle (66 members, 0.6893) — promising until she resolved the members: **bouldering crags ("Cougar Crag," "Well of Poison Area"), indoor golf, F45, chiropractors.** Name-search for infusion/longevity/biohack/peptide/hormone/IV across `/operators` = **0 on every term.** Analytics cover only recovery. `/people` is led by Dr. Bonnie Henry and the Attorney General. `/leads/{id}` **404s.** `/trends` has a "longevity = breakout" row but it's `is_stub`. Last test: QUEST MEDICAL AESTHETICS is tagged a "Municipal recreation facility."

**Top gaps:** (H) the flagship bundle for her category is mis-clustered crags and gyms; (H) no whitespace/scorecard for longevity; (H) leads are uncontactable gyms, `/leads/{id}` broken; (H) trend signal is an admitted fixture; (H) **no medical/regulated vs fitness concept** — a clinic filed as a rec facility; (M) peer cities are Austin/Seattle/Toronto/Melbourne, not the NYC/LA/London she wanted; (M) flat $2,180 proxy, no income/affluence.

**Verdict:** No — wouldn't site on it, wouldn't trust the headline numbers. Respects the sourcing discipline. **Biggest missing thing: a medical/regulated operator layer** (CPSBC/health-authority licensing, real IV/peptide/hormone operators) + income to the catchment math. "Empty dressed up as full."

---

## 4. Sofia — Infrared Sauna & Thermal Wellness Lounge
**Profile:** First-time, design-led founder, ~$120k, walkable high-foot-traffic neighborhood; not a data person, needs legible/trustworthy scoring.

**Story:** Relieved that `/bundles` keeps "Spa & thermal" (0.675, 34 members) **separate** from cold plunge — her #1 question answered. But the members include **Milano Nail Spa, Davie Massage, Third Space Counselling, and "THIRD SPACE CONTRACTING LTD" (a contractor).** Only 3 real thermal operators exist, all `manual_seed`. `/propositions` ranked Marpole top (0.682) — but described it as "100% share of **Richmond**" (Marpole is in Vancouver), and Lower Lonsdale's single "competitor" is the anchor operator itself at 0.0 km. Demand sized on **hair-grooming spend ($215/person)**. `worldwide_match: null`, `first_mover_cities: []`, `/trends` all fixtures, `category-velocity` empty `{}`.

**Top gaps:** (H) trend/first-mover fixtures+empty; (H) category absent from whitespace/scorecards; (H) Marpole→Richmond geo bug; (M-H) bundle polluted with nail salons/contractor; (M-H) "competitors" are massage clinics counting the anchor itself; (M) velocity dead; (M) hair-grooming spend proxy; (M) thermal leader has no contact.

**Verdict:** "Starting-point compass, not a decision tool." Correctly treats saunas as distinct; points to Lower Lonsdale/Downtown. Won't commit $120k on ~0.40 confidence + fixtures + a geo bug. **Biggest missing thing: a real sauna-specific demand + momentum signal** and a clean taxonomy.

---

## 5. Jordan — Yoga & Pilates Studio
**Profile:** Veteran instructor, ~$150k, reformer-Pilates + heated yoga. Knows the category is crowded — *wants the app to confirm saturation and kill false optimism.*

**Story:** `bundle_yoga_pilates` exists (71 members) but scores **0.6919, 3rd of 10**, with `low_supply_density 0.947` and `demand_proxy 0.9912` — the app calls overbuilt yoga/Pilates *under-supplied and high-demand*, generating exactly the false optimism she came to correct. Whitespace/scorecards are 100% recovery — nothing geographic for her. The top fitness proposition calls Downtown "whitespace" while listing 13 competitors within 4 km. 0/1,969 operators match "reformer." The bright spot: `/leads` gave real contactable operators (Oxygen Yoga with email + 2 phones). But Oxygen appears **11×** and Club Pilates **7×** in `/operators` — duplication corrupting the supply counts.

**Top gaps:** (H) scoring says "yes" on a saturated category — the opposite of what she needed; (H) no yoga geographic whitespace at all; (H) "whitespace" headline on a 13-competitor block; (M) reformer Pilates doesn't exist in the taxonomy; (M) Q3/Q4/Q5 empty; (M) heavy operator duplication; (L) taxonomy mismatch (yoga_pilates vs fitness_movement across features).

**Verdict:** "No, not a go/no-go." Fails her one test — it nudges "yes" and labels a crowded block "whitespace." Trusts it as a competitor map + contact directory only. **Biggest missing thing: a saturation/over-supply signal** (per-capita crowding + dedupe) so mature categories score red.

---

## 6. Marcus — Athlete Recovery & Mobility Club
**Profile:** Ex-strength-coach, ~$250k, cryo + compression + percussion + mobility for athletes; B2B2C, co-locate near gyms, partner with teams.

**Story:** Recovery is the #1 region-wide opportunity (whitespace 0.8997, a ranked 14-geo ladder; scorecard even exposes `target_demo_fit` + `transit_access`). The Edmonds prop is a genuinely useful lead (no competitor within 4 km, $543M catchment). Then it broke for his model: search for cryo/normatec/compression/percussion/mobility/athlete = **0 each**; "recovery" here means sauna/cold-plunge/float spa. No proximity/co-location field on operators. `/leads` had 2 recovery leads (both float spas); `/people-graph` is 750 nodes all category `NONE`. Bundle momentum **0.0121** vs `/trends` calling "recovery club" breakout (a fixture).

**Top gaps:** (H) no athlete-recovery vs spa distinction (his services return 0); (H) no proximity/co-location to gyms — his entire siting thesis; (H) no partnership/team/clinic leads; (H) momentum near-zero yet trend says breakout (fixture); (H) Q4/Q5 fixtures; (M) people-graph uncategorized; (M) recovery rests on informal `manual_seed` data.

**Verdict:** Useful for a rough where-to-open shortlist only. **Biggest missing thing: a co-location + B2B-partnership layer** — proximity scoring vs gyms/sports facilities + contactable team/clinic leads.

---

## 7. Elena — Med-Spa / Aesthetics + Wellness
**Profile:** Nurse-injector with a loyal book, ~$400k, injectables/skin/lymphatic/light therapy, high-income women 30–55. Hypothesis going in: the app won't see her.

**Story:** Hypothesis confirmed. `/brief` is all fitness/mind/recovery. `/bundles` has 10 bundles, **none aesthetic** — closest is Spa & thermal (saunas/hotel spas). Name-search across 1,969 ops: botox/injectable/skin/filler/cosmetic/lymphatic/med-spa all **0**; "aesthetic" appears once (QUEST MEDICAL AESTHETICS, tagged community/fitness/retail/spa/nutrition — five categories, none aesthetic). 16-category taxonomy has no aesthetics class. `/people` 93/100 are scraped licence names, 0 contactable. Whitespace/scorecards 100% recovery; `category-velocity` returns `None` for every category. Trends are fixtures omitting injectables entirely.

**Top gaps:** (H) no aesthetics/med-spa/injectables taxonomy at all — structural blindness; (H) the med-spas it does have are misfiled into fitness/community; (H) no scored whitespace/velocity for her category or neighbors; (H) no contactable leads/people in her space; (H/M) trends fixture + omit aesthetics.

**Verdict:** No — "not because it's untrustworthy, but because it cannot see me." The engine works for adjacent categories, so it's a coverage/taxonomy gap. **Biggest missing thing: an Aesthetics/Med-Spa/Injectables category in the taxonomy + bundle/scorecard pipeline.** "I'd check back if they added a beauty-wellness vertical."

---

## 8. Kenji — Mobile / At-Home Massage & Bodywork
**Profile:** RMT-led, app-booked, **no storefront** — serves a service area, ~$40k, route-density growth. His model breaks the location-pin assumption on purpose.

**Story:** Excited that "Allied health & bodywork" is the **#1 bundle of 10** (0.7175, 138 members, demand 0.997 / low-supply 0.9004), reinforced by velocity (148 new ops/30d — real, sourced). Then it broke: opening any RMT (e.g. Alinah Kamani RMT) shows a fixed pin, `venue_class: unknown`, **no `service_area`/`is_mobile` field anywhere.** Whitespace/scorecards 100% recovery — nothing for bodywork. Every proposition is 4-km-radius storefront math; no bodywork proposition exists despite it being the top bundle. `/trends` fixtures, off-category. `/leads` massage entries all `contact: null`. And `/operators?neighborhood=Downtown` returned other neighborhoods — the filter was ignored.

**Top gaps:** (H) no mobile/service-area operator model; (H) whitespace/scorecards don't cover his category; (H) all demand math is storefront-radius — can't union neighborhoods into a route; (H) no bodywork proposition; (M) trends fixtures+off-category; (M) massage leads unreachable; (M) operator filter ignored.

**Verdict:** Useful only to confirm bodywork is high-demand/low-supply/growing at the metro level. **Biggest missing thing: a service-area/mobile-operator model** — represent a business as a catchment, and run whitespace as "where across the metro is coverage thin," not "competitors within 4 km of a pin." "I don't site storefronts."

---

## 9. Aisha — Corporate / Workplace Wellness Provider (B2B)
**Profile:** Ex-HR-tech, ~$200k, sells programs/benefits to **employers**; her "supply" is a partner network of studios. Hoped the app could double as a partner directory + employee-demand read.

**Story:** `/bundles` was a real read on partner supply depth (allied-health and strength deepest; cold-plunge/spa thin). Treated `/operators` as a supplier directory — but `with_contact_count 251/1969 = 12.75%`; the commercial_wellness subset (421) had 145 with contact, **22 with email**, and many entries are numbered-company licence shells ("0569466 BC LTD," null phone). The killer: **no employer demand visible** — `job_velocity_count` = 0 for all categories, no employer/firmographic signal in `/signals`, demand is consumer household recreation spend. `/admin/exports/firmographics|employers|organizations` all rejected — no employer object exists.

**Top gaps:** (H) no employer/workplace demand signal — her whole demand side; (H) no firmographic object (headcount/industry/location); (H) 12.75% contact coverage for a channel play; (M) operator records padded with licence shells; (M) trends fixtures; (M) "people" are influencers not buyers.

**Verdict:** Useful only to build a first-pass partner shortlist. Consumer- and place-oriented to its foundations. **Biggest missing thing: an employer/firmographic layer** — company records with headcount/industry/location + a workplace demand signal.

---

## 10. Hannah — Women's Health & Postnatal Wellness Studio
**Profile:** Physiotherapist + mom, ~$130k, pre/postnatal + pelvic-floor + lactation + community. A **demographic-defined** niche (women 28–42, young families), not a service category.

**Story:** One question: where are young families dense but underserved? Searched all 1,969 operators for prenatal/postnatal/postpartum/pelvic/lactation/doula/midwife/maternal/baby/birth — **0 on every term.** The one adjacent operator (Cedar Pregnancy Care Centre) is filed under generic `allied_health`. No demographic lens to request (`?category=womens_health` → 0). Demand is flat `$2,180 × population` — a young-family block scores identically to a retiree block. `target_demo_fit` exists but is an opaque category-level scalar she can't aim. No census/birth-rate/age-band source in `/admin/source-freshness`. `/trends` fixtures, nothing postnatal.

**Top gaps:** (H) no demographic taxonomy; (H) her one competitor miscategorized & invisible; (H) demand is flat per-capita — no birth-rate/family-density; (H) `target_demo_fit` a black box, not a lever; (H) no global-trend match for her niche; (M) no first-mover intelligence; (M) leads return null category/role/contact.

**Verdict:** No — would actively mislead her; every "whitespace" it shows is whitespace for cold plunge and pilates. **Biggest missing thing: a demographic data layer** (census age-band / households-with-children / birth-rate by neighborhood) wired into the demand proxy + exposed as a tunable filter. "My entire thesis is a demographic question."

---

## 11. Theo — Social Wellness Club (blended concept)
**Profile:** Hospitality founder, ~$350k, "third place" for the sober-curious: alcohol-free social + sauna + cafe + events + co-working. Deliberately spans 4–5 bundles.

**Story:** Thrilled to find `bundle_social_wellness_clubs` (0.6828, 46 members) — until the members turned out to be nail spas, massage, and physio clinics carrying a community tag; **not one true sober social club.** Search for cafe/coworking/sober/social across operators = **0 each**; his multi-pillar concept collapses into one `community_social_wellness` tag. *Where* to open was genuinely useful though: `/propositions` ranked Lower Lonsdale/Edmonds/Downtown/Mount Pleasant with catchment math + named competitors, and `/operators`+`/leads` gave 27 contactable operators (AetherHaus, Ritual Urban Retreat, Kolm Kontrast) for the sauna pillar. `/trends` showed "social wellness" breakout across cities — but all `is_stub` fixtures; momentum 0.0271, `category-velocity` all null.

**Top gaps:** (H) blended concept can't be expressed — cafe/coworking/sober pillars vanish; (H) the bundle bearing his name is a mislabeled grab-bag; (H) global-trend match fabricated (fixtures + `worldwide_match: null`); (H) momentum dead; (M) "who's driving it" half-built (politicians + uncontactable AetherHaus); (M) 12.75% contact coverage; (M) first-mover is a label, not a playbook.

**Verdict:** "Siting/competitor tool yes, concept-validation no." Trusts the official supply side; not the demand/trend/momentum side. **Biggest missing thing: the ability to model a blended, novel concept** — it tells him where the *parts* could go but structurally can't tell him whether the *whole* is an opportunity.
