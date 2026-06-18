## DR1

### Built
- Added the Luminous design-token foundation in `apps/web/src/styles/main.css` and `apps/web/src/lib/theme.ts`, including Space Grotesk/Space Mono, magma score mapping, entity/trust color maps, MapLibre style tokens, `wr-pulse`, and `wr-fade`.
- Added reusable typed components: `SourceChip`, `ConfidenceBar`, `ProvenanceBlock`, `EntityBadge`, `LayerToggle`, `SignalCard`, `ScoreCard`, and `RangeSlider`.
- Rebuilt the global shell with a 56px top bar, logo/title, seven screen tabs, global search button, live status dot, and Vancouver clock.
- Wired browser-history routes for `/`, `/operators/:id`, `/signals`, `/opportunity`, `/people`, `/search`, and `/system`. Non-DR1 routes intentionally render DR2 placeholders only.
- Rebuilt the Console route with a 240px rail, category chips, layer toggles, opportunity/confidence sliders, category velocity card, source freshness card, live MapLibre hero, magma heat layer, signal points, selected rings, heat legend, zoom control, floating inspector, and bottom signal-feed strip.
- Added feed and map selection wiring: operator pin selection populates the inspector and filters the feed; signal card selection sets the signal and flies the map to signal coordinates when available.
- Added the Operator detail route with breadcrumb, header/action row, five metric cards, compact MapLibre trade-area card, competitive set, signal history timeline, provenance drawer, and attributes.
- Derived DR1 detail metrics from existing API data only: supply from whitespace/same-area operators, opportunity from whitespace cells, velocity from category velocity counts/components, rank from same-category confidence ordering, and trade-area competitors from operator coordinates.

### How to Run
- Dev: `pnpm --filter @wellness-radar/web dev`
- Build preview: `pnpm --filter @wellness-radar/web build`
- Main routes: `/`, `/operators/:id`, `/signals`, `/opportunity`, `/people`, `/search`, `/system`

### Verification
- Foundation chunk: `pnpm lint`, `pnpm typecheck`, `pnpm test`, and `pnpm build` passed.
- Console chunk: `pnpm lint`, `pnpm typecheck`, `pnpm test`, and `pnpm build` passed.
- Operator detail chunk: `pnpm lint`, `pnpm typecheck`, `pnpm test`, and `pnpm build` passed.
- Tests now include magma/trust theme checks and signal GeoJSON BC-bound filtering.
- Build note: Vite still reports a chunk-size warning over 500 kB; build completes successfully.

### DOM Notes
- `/` mounts exactly one console screen inside `.wr-screen-area`, with `.wr-console` split into rail/map/feed regions.
- `.wr-inspector` is positioned over the live `.wr-map-stage` and only appears when an operator is selected.
- `/operators/:id` mounts `.wr-operator-detail` with `.wr-metric-strip`, `.wr-detail-grid`, `.wr-detail-left`, and `.wr-detail-right`.
- `/signals`, `/opportunity`, `/people`, `/search`, and `/system` currently mount `.wr-deferred-screen` placeholders by design for DR1.
- No browser screenshot automation was run in this pass.

### Deferred
- Dedicated Signals, Opportunity, People, Search, and System product screens are not implemented in DR1.
- H3 hexbin geometry is still represented by existing whitespace point/circle aggregation; native client-side H3 binning remains for DR2.
- The map still uses the repo's built-in empty/dark MapLibre style plus app data layers; no external basemap or tile provider was added.
- The operator detail export action downloads the current operator JSON client-side; no server export API was added.

### DR2 Pickup
- Build the dedicated `/signals` screen with filter rail, stream, detail rail, trust tier filters, and AI enrichment labeling.
- Build `/opportunity` with true client-side H3 display aggregation, ranked scorecards, method caveats, and fixture-backed trend labels.
- Build `/people` with the full Sigma graph inspector, community legend, influence components, and public-data governance caveat.
- Build `/search` cross-object results across operators, signals, people, and opportunity scorecards using existing list endpoints.
- Build `/system` as the internal design-system reference route using the reusable DR1 components.
- Add browser-level visual/DOM verification for desktop and mobile once DR2 screens are present.

## DR2

### Built
- Replaced the DR1 `/signals` placeholder with a three-column Luminous Signals screen: type filter rail, trust-tier toggles, confidence slider, reverse-chronological day groups, source-backed signal cards, and a detail rail with provenance plus AI-enrichment labeling as "Enrichment, not a source of truth."
- Converted the whitespace/opportunity map overlay to client-side display hexbins. The new `heatmapToHexbinFeatureCollection` bins existing `geo_code` / `geo_name` whitespace cells with lat/lng into a pseudo-H3 axial grid in the browser; it does not add native H3, schema fields, or backend calls.
- Replaced `/opportunity` with a two-column hexbin-map/ranked-list surface: category pills, hottest-cell callout, magma legend and attractiveness caveat, ranked reusable `ScoreCard`s, component bars, and peer-city fixture-backed warning label.
- Rebuilt `/people` with a full Sigma graph route, Louvain community coloring, centrality sizing, high-centrality labels, community legend, public-professional governance caveat, and a right-side inspector with influence components, explanation, correction-request language, provenance, and linked-operator action when existing records support it.
- Added `/search` as a cross-object search over currently loaded operators, signals, people, and opportunity scorecards. Every row carries source chip, confidence value, and freshness age, and rows route to the relevant product screen.
- Added `/system` as a living Luminous design-system reference with token swatches, type scale, SourceChip tiers, ConfidenceBar examples, feed item, controls, and MapLibre style tokens.
- Extended cross-cutting behavior: `/` focuses or opens search, `Esc` closes search/selection, Signal and Opportunity routes have <=1100px single-column layouts, and the MapLibre fly-to/cluster behavior from DR1 remains intact.

### Built vs Handoff Checklist
- Screen 1 Console: built in DR1 and retained. MapLibre remains live with recolored built-in style, operator clustering, selected inspector, feed strip, sliders, layer toggles, and magma heat.
- Screen 2 Operator detail: built in DR1 and retained. Uses existing operator, signal, whitespace, and velocity fields only; no visit or foot-traffic metrics were introduced.
- Screen 3 Signals: built in DR2. Filters, stream, detail rail, provenance, AI-enrichment warning, confidence slider, source chips, magma confidence values, and operator-open action are present.
- Screen 4 Opportunity: built in DR2. Hexbin display aggregation, hottest-cell callout, ranked scorecards, component bars, magma legend, method caveat, and fixture-backed peer-city warning are present.
- Screen 5 People: built in DR2. Sigma graph, Louvain community colors, centrality sizing, high-centrality labels, governance caveat, explainable influence inspector, provenance, and correction-request language are present.
- Screen 6 Search: built in DR2. Centered search bar, entity type pills with counts, grouped rows, route actions, and citation row model are present.
- Screen 7 System: built in DR2. Token, type, component, and map-style reference sections are present at `/system` and `/design-system`.

### Verification
- Signals chunk: `pnpm lint`, `pnpm typecheck`, `pnpm test`, and `pnpm build` passed.
- Opportunity chunk: `pnpm lint`, `pnpm typecheck`, `pnpm test`, and `pnpm build` passed.
- People chunk: `pnpm lint`, `pnpm typecheck`, `pnpm test`, and `pnpm build` passed.
- Search/System chunk: `pnpm lint`, `pnpm typecheck`, `pnpm test`, and `pnpm build` passed.
- Test count after DR2: 2 test files, 9 tests passed. Added coverage for client-side whitespace hexbin aggregation and non-BC whitespace filtering.
- Build note: Vite still reports the existing large chunk warning over 500 kB; the build completes successfully.

### Faithful vs Approximated
- Faithful: routes, shell, tokens, typography, magma score mapping, source/provenance surfaces, trust tiers, signal filters, opportunity caveats, fixture-backed warning, and no-new-data-contract constraint.
- Faithful: MapLibre remains live with the repo's built-in style and no external tiles or paid dependencies.
- Approximated: "H3 hexbin" is implemented as a browser-only axial hex display grid over existing whitespace lat/lng cells, not native H3 indexing, matching the handoff's no-schema-change constraint.
- Approximated: Sigma node glow/ring is represented with color, sizing, label threshold, canvas drop-shadow, and graph backdrop. Sigma's default renderer does not draw per-node custom halo rings without custom node programs.
- Approximated: Search operates over the currently loaded list endpoint data in the client rather than adding a backend search endpoint.

### Honest Gaps
- No browser screenshot automation was run for desktop/mobile visual diffing in this pass.
- People graph selected-node highlighting is inspector-driven; there is not yet a precise on-canvas selected ring around the clicked node.
- Opportunity hexbin cells require whitespace records with lat/lng. Records without coordinates remain available in scorecards but cannot render as map polygons.

## Final Status

### How to Run
- Dev: `pnpm --filter @wellness-radar/web dev`
- Build: `pnpm --filter @wellness-radar/web build`
- Main routes: `/`, `/operators/:id`, `/signals`, `/opportunity`, `/people`, `/search`, `/system`

### How to Verify
- Run the full suite from the repo root: `pnpm lint && pnpm typecheck && pnpm test && pnpm build`.
- Route smoke checks: open `/`, `/signals`, `/opportunity`, `/people`, `/search`, and `/system`; press `/` to focus/open search; press `Esc` to close search or clear inspectors.
- Data-contract check: DR2 changes are limited to `apps/web`, docs, and web tests. No changes were made to `apps/api`, `apps/jobs`, `db`, or `packages`.

### Current Branch State
- Branch: `design/luminous`.
- DR2 committed in small logical commits after each verified chunk.
- No remotes were pushed and no secrets were touched.
