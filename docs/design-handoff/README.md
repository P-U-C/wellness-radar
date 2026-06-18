# Handoff: Wellness Radar — "Luminous" visual + interaction overhaul

## Overview
A full visual and interaction redesign of the **Vancouver Wellness Radar** map-first
market-intelligence console. Same product, same data contracts — new instrument-grade
dark UI. Four entity types (**Operator · Signal · People · Opportunity**), every record
source-backed, **provenance is first-class on every surface**.

The chosen direction is **"Luminous"** (one of three concepts explored): modern
geospatial aesthetic (Felt / Kepler), map-as-hero, glowing magma H3 hexbins, per-entity
color coding, floating Placer-style inspector, and a chronological signal feed.

---

## About the design files
The files in this bundle are **design references created in HTML** — high-fidelity
prototypes showing the intended look, layout, and behavior. **They are not production
code to copy.** The task is to **recreate these designs in the existing `apps/web`
codebase** (React + TypeScript + Vite + MapLibre GL + Sigma.js), reusing its established
component structure, data layer, and libraries.

- `Wellness Radar — Console.dc.html` — the deliverable: all 6 screens + the design
  system, behind a top-nav screen switcher. (It is a single self-contained HTML file;
  open in any browser. Internally it uses a small custom template runtime — ignore that;
  read it as a visual spec.)
- `reference/Wellness Radar — Directions (3 concepts).dc.html` — the original 3 concept
  directions (Obsidian / Luminous / Terminal). Context only; **build Luminous**.
- `tokens.css` — all design tokens as CSS custom properties.
- `theme.ts` — the same tokens as a TS module, plus a `magma(t)` interpolator and
  MapLibre style tokens.

## Fidelity
**High-fidelity.** Colors, typography, spacing, and interactions are final. Recreate the
UI pixel-faithfully using the codebase's existing libraries (MapLibre, Sigma, React).
Where the prototype draws a *stylized SVG map of Metro Vancouver*, that is a stand-in for
the **real MapLibre map** — keep the live map and the built-in style, but **recolor** it
to the `mapStyle` tokens in `theme.ts`.

---

## Stack & data — keep intact
No backend or data-contract changes. The redesign consumes the **existing** API and
types verbatim (`apps/web/src/lib/api.ts`):

- `Operator`, `Signal`, `Person` each carry `source_refs: SourceRef[]`,
  `confidence_score: number`, `freshness_at` / `freshness_age_hours`.
- `SourceRef { source_name, url, trust_tier, seen_at, licence }` — drives every source chip.
- `trust_tier` ∈ `official | reputable_press | commercial_api | community | informal | ai_inferred`.
- Opportunity: `OpportunityHeatmapCell` (`/analytics/whitespace`),
  `OpportunityScorecard` (`/analytics/opportunity-scorecards`),
  `CategoryVelocity` (`/analytics/category-velocity`).
- People graph: `GraphNode { node_type, centrality, community, x, y }` + `GraphEdge`.
- 11 `CATEGORIES`, 6 `OPERATOR_STATUSES` (`canonical.py`).

### ⚠ Data-model constraints to flag to the team
1. **No visit / foot-traffic metrics exist.** The operator detail looks Placer-like but
   uses only real fields: neighborhood `supply_count` + `opportunity_score`
   (`/analytics/whitespace`) and `category-velocity`. "Rank in category" and "trade area"
   are derived client-side from existing data — **do not invent visit counts**; that would
   need a new commercial source + adapter + source-rights row.
2. **Hexbins are a display aggregation.** Opportunity/whitespace data is keyed to
   `geo_code` / `geo_name` (CSD/CMA level) with optional `lat/lng` — **not** native H3.
   Render heat by binning those cells into an H3 grid client-side; no schema change.
3. **Peer-city trends are fixture-backed** (`is_stub: true`) — keep them labelled
   "fixture" with the warn color, as the API already marks them.
4. AI-enriched fields (`why_it_matters`, `ai_*`) must stay visibly labelled
   **"enrichment, not a source of truth"** (people color / `--wr-people`).

---

## Global shell

**Layout:** full-viewport flex column. `height: 100vh; overflow: hidden`.
- **Top bar** — 56px, `--wr-panel`, bottom border `--wr-line`. Left: hexagon logo mark
  (operator accent) + "Wellness Radar" / "METRO VANCOUVER". Center-left: **screen nav**
  (7 tabs). Right: global search button (opens Search screen) + live status dot (`--wr-ok`,
  pulsing) + clock.
- **Screen area** — `flex: 1; min-height: 0`. Exactly one screen mounted at a time.

**Nav tabs:** `Console · Operators · Signals · Opportunity · People · Search · System`.
- Active: bg `--wr-raised`, text `--wr-text`, `box-shadow: inset 0 0 0 1px --wr-line-2`.
- Inactive: transparent, text `--wr-muted`.
- Font: 600 12.5px Space Grotesk. Height 34px, padding 0 14px, radius `--wr-r-md`.

**State management (App-level):**
- `screen: 'console' | 'operator' | 'feed' | 'opportunity' | 'people' | 'search' | 'system'`.
- `selectedOperatorId`, `category`, `peopleSort`, `minConfidence`, `layers` (visibility
  per entity type), `trustFilter`, `signalTypeFilter`. Most already exist in `App.tsx`.
- The prototype's switcher is a stand-in for **routing** — implement as routes
  (`/`, `/operators/:id`, `/signals`, `/opportunity`, `/people`, `/search`) if you prefer.

---

## Screens

### 1 — Console  → `App.tsx` + `OperatorMap.tsx` + `SignalFeed.tsx` + `EntityDrawer.tsx`
**Purpose:** overview; "where it's happening" beside "what's happening now."
**Layout:** grid `1fr / 240px 1fr` for (rail · map), with a **bottom feed strip** row
(`grid-template-rows: 1fr 158px`).
- **Left rail** (`--wr-panel`, right border `--wr-line`, padding 16px 14px, gap 16px):
  - **LAYERS** — 4 toggle rows (Operators/Signals/People/Opportunity). Active row uses the
    entity's `*-soft` bg + `*-border`, an 8px glowing dot (`box-shadow: 0 0 6px <accent>`),
    name (600 13px), and a mono count/state. Off row uses `--wr-raised`/`--wr-line-2`.
  - **CATEGORY** chips — active chip solid `--wr-operator` w/ `#080D18` text; others
    `--wr-raised` + `--wr-line-2`, `--wr-text-dim`. radius `--wr-r-sm`, padding 6px 10px.
  - Two **range sliders** ("OPPORTUNITY ≥", "MIN CONFIDENCE") — 6px track `--wr-raised`,
    filled portion magma gradient (opportunity) or solid `--wr-ok` (confidence), 14px
    white thumb with 3px `--wr-panel` ring.
  - **CATEGORY VELOCITY · 90D** card — big `+18%` (`--wr-ok`) + area sparkline.
  - **SOURCE FRESHNESS** card — per-source dot (ok/warn) + name + mono age.
- **Map hero** (`#070b14`, `position: relative`): the real MapLibre map recolored to
  `mapStyle`. Overlays:
  - **Floating inspector** — top/right/bottom 14px, width **330px**,
    `background: rgba(15,22,34,.86)`, `backdrop-filter: blur(10px)`, border `--wr-line-2`,
    radius `--wr-r-lg`, `--wr-shadow-pop`. Contents = condensed operator detail
    (eyebrow OPERATOR·NEW, name 21px, 3 metric tiles, provenance block w/ source chips +
    magma confidence bar, related signals). "OPEN ↗" button → Operator detail screen.
  - **Heat legend** (bottom-left) — magma gradient bar 140×10, "low → high", pin key.
  - **Zoom control** (bottom-right) — stacked +/− 30px cells.
- **Bottom feed strip** (`--wr-panel`, top border): label "SIGNAL FEED · LAST 24H" +
  "view all ↗" (→ Signals), then a **horizontal row of signal cards** (each 232px,
  `--wr-raised`, top border 2px in the signal-type color, radius `--wr-r-md`), ending in a
  dashed "+N earlier" tile. Type colors: new-operator `--wr-signal`, press `--wr-operator`,
  whitespace `--wr-opportunity`, recall `--wr-danger`.

**Interactions:** click pin → select operator, fly map, populate inspector, filter feed.
Click feed card → fly map to signal. Layer toggles show/hide map layers. Category +
sliders reactively filter (already wired in `App.tsx`'s `visibleOperators`/`visibleSignals`).

### 2 — Operator detail  → new route, lift from `EntityDrawer.tsx` + `OpportunityPanel.tsx`
**Purpose:** full operator record with deep provenance (Placer-style).
**Layout:** scroll page, `max-width: 1180px; margin: 0 auto; padding: 26px 28px`.
- Breadcrumb (mono) `← Console / Operators / <name>`.
- Header: status badges (OPERATOR pill in operator-soft; status pill e.g. NEW in
  signal-soft), **title 34px/700 -0.02em**, mono address line. Right: "View on map"
  (secondary) + "Export record" (primary).
- **Metric strip** — 5 cards `grid-template-columns: repeat(5,1fr); gap 12px`, each
  `--wr-panel`/`--wr-line`, radius `--wr-r-lg`, padding 16px: number 28px/700 (colored by
  meaning — neutral, `--wr-opportunity`, `--wr-signal`, neutral, magma), mono caption.
  Values: recovery supply `7`, opportunity `0.71`, velocity `+18%`, rank `#2`, confidence `0.92`.
- Two-column `1.55fr / 1fr`:
  - **Left:** map+competitive-set card (mini MapLibre, "TRADE AREA · 1.5KM" pill, then a
    list of nearby operators with distance/status + a small share bar);
    **signal history** timeline (vertical connector dots colored by signal type, title,
    `why_it_matters`, source chip + age + conf).
  - **Right (provenance drawer):** "PROVENANCE / VERIFIED 1H AGO", one card per source
    (`source_name`, tier in tier color, `licence`/match note, "source ↗" → `url`), then a
    **magma confidence bar** + a plain-language trust note ("3 independent sources ·
    BC-gate passed · no Washington-State contamination"). Below: **ATTRIBUTES** definition
    list (status, category chips, org id, geocode, neighborhood — mono for machine values).

### 3 — Signals  → `SignalFeed.tsx`
**Purpose:** dedicated reverse-chronological feed.
**Layout:** grid `236px 1fr 360px` (filters · stream · detail).
- **Filters rail:** SIGNAL TYPE (5 toggle rows, entity-soft bg, colored dot, mono count),
  TRUST TIER list (6 tiers, swatch + count), CONFIDENCE ≥ slider.
- **Stream:** header (title 18px + "47 signals · last 24h" + sort control). Day dividers
  ("TODAY"/"YESTERDAY" mono label + hairline). **Signal cards:** `--wr-panel`, left border
  3px in type color, radius `--wr-r-lg`, padding 15px 17px. Type badge + neighborhood +
  age, **title 16px/600**, `why_it_matters` (13px/1.5 `--wr-text-body`), footer source
  chip + `conf <value>` (value colored by magma band) + "fly to ↗".
- **Detail rail:** selected signal — type badge, title 18px, summary, PROVENANCE card
  (source chip + magma conf bar), **AI ENRICHMENT** card (purple, "not a source of truth"),
  "Open operator record →" (→ screen 2).

### 4 — Opportunity  → `OperatorMap.tsx` (hexbin) + `OpportunityPanel.tsx`
**Purpose:** white-space density + ranked scorecards.
**Layout:** grid `1fr 460px` (hexbin map · ranked list).
- **Map:** MapLibre with **H3 hexbin heat** only (no operator pins), fill via `magma()`,
  `hexFillOpacity(v)`. Title overlay + category pills (Recovery active). A **callout
  bubble** on the hottest cell (`--wr-opportunity` border + soft glow): name, score (mono),
  "N operators · pop · demand >> supply". Bottom-left magma legend with caveat
  "supply-demand signal, not guaranteed attractiveness".
- **Ranked list** (`--wr-panel`, left border): header "Ranked opportunities · 22 areas ·
  CSD level". **Scorecards** (`--wr-raised`, radius `--wr-r-lg`, padding 14px): rank (mono),
  name (15px/700), **score 22px/700** colored by magma band; 3 mini stat tiles
  (supply/pop/demandΔ); **COMPONENT BREAKDOWN** — labeled bars (undersupply / demand grow /
  access gap) each value-colored; footer source chip + verified age + conf. Top card gets a
  faint opportunity glow. Footer: method note + "peer-city inputs fixture-backed".

### 5 — People  → `PeopleGraph.tsx` (Sigma.js) + `PeopleLeaderboard.tsx`
**Purpose:** public professional relationship graph + explainable influence.
**Layout:** grid `1fr 380px` (graph · inspector).
- **Graph:** Sigma/graphology force layout. Nodes colored by **Louvain `community`**
  (4 community colors map to operator/people/press/civic = `--wr-operator / --wr-people /
  --wr-opportunity / --wr-signal`), **sized by `centrality`**, ringed (2px) on a
  `--wr-panel` fill with a soft glow halo; labels (600 12px) on high-centrality nodes only.
  Edges `--wr-line-2`, ~0.7 opacity. Overlays: title, COMMUNITIES legend, and the governance
  caveat "public professional data only · no patient/clinical/social/LinkedIn".
- **Inspector:** avatar (ringed initials), PERSON·OPERATOR eyebrow, name, role line.
  **INFLUENCE SCORE** card — big value (`--wr-operator`) + component bars (centrality /
  reach / recency). **WHY THIS PERSON APPEARS** (explainable text; mentions reversible
  correction-requests in `--wr-people`). PROVENANCE card (source chips + magma conf).
  Actions: "Linked operator →" (primary) + "Flag" (people-tinted).

### 6 — Search  → new; cross-object over existing list endpoints
**Purpose:** one query across all four entity types (Perplexity/Bloomberg citation model).
**Layout:** centered `max-width: 900px`.
- **Search bar:** 54px, `--wr-panel`/`--wr-line-2`, radius `--wr-r-xl`, soft accent ring;
  search icon (operator accent), query text 16px, blinking caret, "esc" hint.
- **Type filter pills:** All / Operators / Signals / People / Opportunity — each in its
  entity color-soft with a mono count.
- **Result groups** (one per entity type): colored dot + mono section label + hairline,
  then result rows (`--wr-panel`/`--wr-line`, radius `--wr-r-lg`). Each row: title +
  optional status badge + mono subtitle on the left; on the right a **source chip** +
  "conf <value> · <age>". Rows are buttons → the relevant detail screen.

### 7 — System (design system reference)
A living token/component sheet — not a product screen, but ship it as an internal
`/design-system` route if useful. Sections: color tokens (surfaces, entity accents, magma),
type scale, component library (source chip ×6 tiers, confidence indicator, feed item,
controls), and map style + spacing tokens. Mirrors `tokens.css` / `theme.ts`.

---

## Reusable components (build these first)
| Component | Props (from existing types) | Notes |
|---|---|---|
| `SourceChip` | `SourceRef` | dot in `trustTier[ref.trust_tier]`, `source_name`, tier label, age from `seen_at`; click → `url`. mono 11px, `--wr-raised`/`--wr-line-2`, radius `--wr-r-sm`. |
| `ConfidenceBar` | `score: number` | track `--wr-raised`; fill width `score*100%`, gradient magma slice; mono value colored by `magma(score)`. |
| `ProvenanceBlock` | `source_refs`, `confidence_score`, `freshness_age_hours` | "VERIFIED Nh ago" (ok if fresh, warn if past SLA), stacked SourceChips, ConfidenceBar, trust note. |
| `EntityBadge` | `type` | eyebrow pill: glowing dot + label in entity color-soft. |
| `LayerToggle` | `type`, `count`, `on` | rail row described in Console. |
| `SignalCard` | `Signal` | type→color map; left/top accent border; badge + age + title + `why_it_matters` + SourceChip. |
| `ScoreCard` | `OpportunityScorecard` | rank, name, magma score, stat tiles, component breakdown bars. |
| `RangeSlider` | value | 6px track, magma or `--wr-ok` fill, 14px white thumb + panel ring. |

`entity-type → color` and `trust_tier → color` maps live in `theme.ts`. The magma ramp is
the single source for all "score → color" mappings (confidence, density, opportunity).

---

## Interactions & motion
- **Pulse** (`@keyframes wr-pulse`, 2.4s) on live status + glowing layer dots: scale 1→1.4,
  opacity .35→1.
- **Fade-in** (`@keyframes wr-fade`, .4s ease) on newly-arriving feed items: translateY(6px)+opacity.
- Map fly-to on pin/feed select (MapLibre `flyTo`, ~600ms ease).
- Floating inspector: `backdrop-filter: blur(10px)`; appears on selection.
- Hover (recommended, not in static mock): cards lighten border to `--wr-line-2`; buttons
  brighten; pins scale ~1.2.
- Sliders, toggles, chips are real controls — wire to existing `App.tsx` filter state.

## Accessibility
- Dark-mode contrast: body text `--wr-text` / `--wr-text-dim` on `--wr-panel` ≥ 7:1.
  Keep mono meta at `--wr-muted` (≥ 4.5:1) — don't drop below `--wr-faint` for essential text.
- **Color-blind-safe heat:** magma carries luminance as well as hue — never encode a value
  by hue alone; always pair with the numeric (mono) value, as the mocks do.
- Keyboard: nav tabs, layer toggles, sliders, list rows and chips are focusable buttons;
  `/` focuses global search; `esc` closes inspector/search. Provide visible focus rings
  (2px `--wr-operator`).
- Don't rely on entity color alone to distinguish object types — each also has a label/glyph.

## Performance
- **Density over pins:** above the cluster threshold render the **H3 hexbin heat layer**
  instead of thousands of individual operator pins (already the design intent). Keep
  MapLibre clustering for the operator layer at high zoom.
- Hexbin: precompute per-cell scores; recolor with `magma()` on the GPU fill expression.

## Responsive
Map-first on desktop. Below ~1100px: collapse to single column — rail becomes a top sheet,
inspector becomes a bottom sheet over the map, feed strip stacks under the map (the existing
`main.css` already has a `@media (max-width: 1100px)` pattern to follow).

---

## Design tokens
See `tokens.css` (CSS custom properties) and `theme.ts` (TS + `magma()` + MapLibre style
tokens). Summary: base `#080D18`; panels `#0F1622`/`#16202E`; lines `#212D3D`/`#2B3A4D`;
text `#EAF0F7`/`#C2CEDB`/`#8595A8`/`#5A6A7E`; entity `#38BDF8`/`#F5A524`/`#A78BFA`/`#34D399`;
danger `#F87171`; magma `#1b0c33→#fcfdbf`. Type: Space Grotesk (UI) + Space Mono (all
numerics/IDs/coords/timestamps). Radius 4/6/8/11/13/pill. Spacing 6/10/14/18/22/28.

## Assets
- **Fonts:** Space Grotesk + Space Mono (Google Fonts). Swap to whatever the repo bundles;
  the key rule is *a mono face for every machine value*.
- **Icons:** the repo already uses `lucide-react`; the mock's inline SVGs (search, hexagon
  logo, external-link, chevrons) all have lucide equivalents.
- **Map:** no external tiles required — recolor the existing built-in MapLibre style.
- No raster assets; no Anthropic/third-party brand assets used.

## Files in this bundle
- `Wellness Radar — Console.dc.html` — all 6 screens + design system (the spec).
- `reference/Wellness Radar — Directions (3 concepts).dc.html` — the 3 explored directions.
- `tokens.css` — design tokens (CSS custom properties).
- `theme.ts` — design tokens + `magma()` + MapLibre style tokens (TypeScript).

### Existing repo files to recreate the designs in
- `apps/web/src/app/App.tsx` — shell, state, data orchestration.
- `apps/web/src/features/map/OperatorMap.tsx` — map, pins, hexbins, legend.
- `apps/web/src/features/feed/SignalFeed.tsx` — Console feed strip + Signals screen.
- `apps/web/src/features/entities/EntityDrawer.tsx` — floating inspector + Operator detail.
- `apps/web/src/features/analytics/OpportunityPanel.tsx` + `TrendTiles.tsx` — Opportunity.
- `apps/web/src/features/graph/PeopleGraph.tsx` + `people/PeopleLeaderboard.tsx` — People.
- `apps/web/src/styles/main.css` — replace `:root` with `tokens.css`.
- `apps/web/src/lib/api.ts` — types (unchanged) the components bind to.
