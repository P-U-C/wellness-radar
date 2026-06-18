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
