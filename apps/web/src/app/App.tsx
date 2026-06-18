import { Hexagon, Search } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { LayerToggle, RangeSlider } from "../components";
import { EntityDrawer } from "../features/entities/EntityDrawer";
import { OperatorDetail } from "../features/entities/OperatorDetail";
import { OpportunityPanel } from "../features/analytics/OpportunityPanel";
import { SignalFeed } from "../features/feed/SignalFeed";
import { PeopleGraph } from "../features/graph/PeopleGraph";
import { KioskMode } from "../features/kiosk/KioskMode";
import { OperatorMap, type MapLayers } from "../features/map/OperatorMap";
import { PeopleLeaderboard } from "../features/people/PeopleLeaderboard";
import { SearchScreen } from "../features/search/SearchScreen";
import { SystemScreen } from "../features/system/SystemScreen";
import {
  fetchCategoryVelocity,
  fetchObservability,
  fetchOperators,
  fetchOpportunityScorecards,
  fetchPeople,
  fetchPeopleGraph,
  fetchSignals,
  fetchSourceFreshness,
  fetchSourceRuns,
  fetchTrends,
  fetchWhitespace,
  type CategoryVelocity,
  type GraphEdge,
  type GraphNode,
  type ObservabilitySummary,
  type Operator,
  type OpportunityHeatmapCell,
  type OpportunityScorecard,
  type Person,
  type Signal,
  type SourceFreshness,
  type SourceRun,
  type TrendTile
} from "../lib/api";
import { formatAgeFromHours, formatScore, sentenceCase } from "../lib/format";
import { isInBcBounds } from "../lib/geo";

const CATEGORIES = [
  { value: "all", label: "All" },
  { value: "recovery_contrast_therapy", label: "Recovery" },
  { value: "fitness_movement", label: "Fitness" },
  { value: "spa_thermal", label: "Spa" },
  { value: "allied_health", label: "Allied" },
  { value: "mind_meditation", label: "Mind" },
  { value: "community_social_wellness", label: "Social" }
];

type Screen = "console" | "operator" | "feed" | "opportunity" | "people" | "search" | "system";

type RouteState = {
  screen: Screen;
  operatorId: string | null;
};

const SCREEN_TABS: Array<{ screen: Screen; label: string }> = [
  { screen: "console", label: "Console" },
  { screen: "operator", label: "Operators" },
  { screen: "feed", label: "Signals" },
  { screen: "opportunity", label: "Opportunity" },
  { screen: "people", label: "People" },
  { screen: "search", label: "Search" },
  { screen: "system", label: "System" }
];

const kioskMode = new URLSearchParams(window.location.search).get("mode") === "kiosk";

export function App() {
  const [operators, setOperators] = useState<Operator[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [sourceRuns, setSourceRuns] = useState<SourceRun[]>([]);
  const [sourceFreshness, setSourceFreshness] = useState<SourceFreshness[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [heatmapCells, setHeatmapCells] = useState<OpportunityHeatmapCell[]>([]);
  const [scorecards, setScorecards] = useState<OpportunityScorecard[]>([]);
  const [velocity, setVelocity] = useState<CategoryVelocity[]>([]);
  const [trends, setTrends] = useState<TrendTile[]>([]);
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([]);
  const [observability, setObservability] = useState<ObservabilitySummary | null>(null);
  const [selectedOperatorId, setSelectedOperatorId] = useState<string | null>(null);
  const [selectedSignalId, setSelectedSignalId] = useState<string | null>(null);
  const [selectedGraphNodeId, setSelectedGraphNodeId] = useState<string | null>(null);
  const [category, setCategory] = useState("all");
  const [peopleSort] = useState("influence");
  const [minConfidence, setMinConfidence] = useState(0.6);
  const [minOpportunity, setMinOpportunity] = useState(0.55);
  const [layers, setLayers] = useState<MapLayers>({
    operators: true,
    signals: true,
    people: false,
    opportunity: true
  });
  const [trustFilter, setTrustFilter] = useState("all");
  const [signalTypeFilter, setSignalTypeFilter] = useState("all");
  const [route, setRoute] = useState<RouteState>(() => routeFromPath(window.location.pathname));
  const [clock, setClock] = useState(() => new Date());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const screen = route.screen;

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const analyticsCategory = category === "all" ? "recovery_contrast_therapy" : category;
      const [
        operatorData,
        signalData,
        runData,
        freshnessData,
        peopleData,
        heatmapData,
        scorecardData,
        velocityData,
        trendData,
        graphData,
        observabilityData
      ] = await Promise.all([
        fetchOperators(category),
        fetchSignals(),
        fetchSourceRuns(),
        fetchSourceFreshness(),
        fetchPeople(peopleSort),
        fetchWhitespace(analyticsCategory),
        fetchOpportunityScorecards(analyticsCategory),
        fetchCategoryVelocity(analyticsCategory),
        fetchTrends(),
        fetchPeopleGraph(),
        fetchObservability()
      ]);
      setOperators(operatorData);
      setSignals(signalData);
      setSourceRuns(runData);
      setSourceFreshness(freshnessData);
      setPeople(peopleData);
      setHeatmapCells(heatmapData);
      setScorecards(scorecardData);
      setVelocity(velocityData);
      setTrends(trendData);
      setGraphNodes(graphData.nodes);
      setGraphEdges(graphData.edges);
      setObservability(observabilityData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load API data");
    } finally {
      setLoading(false);
    }
  }, [category, peopleSort]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    const timer = window.setInterval(() => setClock(new Date()), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    function onPopState() {
      setRoute(routeFromPath(window.location.pathname));
    }
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    if (route.operatorId) {
      setSelectedOperatorId(route.operatorId);
    }
  }, [route.operatorId]);

  const navigate = useCallback((path: string) => {
    window.history.pushState(null, "", path);
    setRoute(routeFromPath(path));
  }, []);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const isTyping = target?.tagName === "INPUT" || target?.tagName === "TEXTAREA" || target?.isContentEditable;
      if (event.key === "/" && !isTyping) {
        event.preventDefault();
        if (screen === "search") {
          window.dispatchEvent(new Event("wr-focus-search"));
          return;
        }
        navigate("/search");
      }
      if (event.key === "Escape") {
        if (screen === "search") {
          navigate("/");
        } else {
          setSelectedOperatorId(null);
          setSelectedSignalId(null);
          setSelectedGraphNodeId(null);
        }
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [navigate, screen]);

  const visibleOperators = useMemo(
    () =>
      operators.filter(
        (operator) =>
          operator.source_refs.length > 0 &&
          isInBcBounds(operator.lat, operator.lng) &&
          operator.confidence_score >= minConfidence &&
          (category === "all" || operator.categories.includes(category))
      ),
    [operators, category, minConfidence]
  );

  const visibleHeatmapCells = useMemo(
    () =>
      heatmapCells
        .filter((cell) => cell.opportunity_score >= minOpportunity)
        .filter((cell) => cell.confidence_score >= minConfidence)
        .sort((a, b) => b.opportunity_score - a.opportunity_score),
    [heatmapCells, minConfidence, minOpportunity]
  );
  const visibleScorecards = useMemo(
    () =>
      scorecards
        .filter((scorecard) => scorecard.opportunity_score >= minOpportunity)
        .filter((scorecard) => scorecard.confidence_score >= minConfidence)
        .sort((a, b) => b.opportunity_score - a.opportunity_score),
    [minConfidence, minOpportunity, scorecards]
  );

  const visibleSignals = useMemo(() => {
    const operatorIds = new Set(visibleOperators.map((operator) => operator.id));
    return signals
      .filter((signal) => signal.source_refs.length > 0)
      .filter((signal) => signal.confidence_score >= minConfidence)
      .filter((signal) => trustFilter === "all" || signal.trust_tier === trustFilter)
      .filter((signal) => signalTypeFilter === "all" || signal.type === signalTypeFilter)
      .filter((signal) => !signal.related_operator_id || operatorIds.has(signal.related_operator_id))
      .sort((a, b) => Date.parse(b.occurred_at) - Date.parse(a.occurred_at));
  }, [minConfidence, signalTypeFilter, signals, trustFilter, visibleOperators]);

  const sourceBackedSignals = useMemo(
    () =>
      signals
        .filter((signal) => signal.source_refs.length > 0)
        .filter((signal) => !signal.related_operator_id || operators.some((operator) => operator.id === signal.related_operator_id))
        .sort((a, b) => Date.parse(b.occurred_at) - Date.parse(a.occurred_at)),
    [operators, signals]
  );

  const feedSignals = useMemo(() => {
    if (!selectedOperatorId) {
      return visibleSignals;
    }
    return visibleSignals.filter((signal) => signal.related_operator_id === selectedOperatorId);
  }, [selectedOperatorId, visibleSignals]);

  const selectedOperator = visibleOperators.find((operator) => operator.id === selectedOperatorId) ?? null;
  const detailOperators = useMemo(
    () =>
      operators.filter(
        (operator) =>
          operator.source_refs.length > 0 &&
          isInBcBounds(operator.lat, operator.lng) &&
          (category === "all" || operator.categories.includes(category))
      ),
    [category, operators]
  );
  const routedOperator = route.operatorId
    ? operators.find((operator) => operator.id === route.operatorId) ?? null
    : null;
  const detailOperator =
    routedOperator ??
    detailOperators.find((operator) => operator.id === selectedOperatorId) ??
    detailOperators[0] ??
    null;
  const detailSignals = detailOperator
    ? signals
        .filter((signal) => signal.related_operator_id === detailOperator.id)
        .filter((signal) => signal.source_refs.length > 0)
    : [];
  const selectedOperatorSignals = selectedOperator
    ? visibleSignals.filter((signal) => signal.related_operator_id === selectedOperator.id)
    : [];
  const nearbyOperators = selectedOperator
    ? visibleOperators.filter(
        (operator) =>
          operator.id !== selectedOperator.id &&
          operator.neighborhood !== null &&
          operator.neighborhood === selectedOperator.neighborhood
      )
    : [];
  const selectedOpportunity = selectedOperator
    ? findOpportunityForOperator(selectedOperator, visibleHeatmapCells) ??
      findOpportunityForOperator(selectedOperator, heatmapCells)
    : null;
  const supplyCount =
    selectedOpportunity?.supply_count ??
    (selectedOperator
      ? visibleOperators.filter(
          (operator) =>
            operator.id !== selectedOperator.id &&
            operator.neighborhood === selectedOperator.neighborhood &&
            hasCategoryOverlap(operator, selectedOperator)
        ).length
      : null);
  const opportunityScore = selectedOpportunity?.opportunity_score ?? null;
  const velocityItem = velocity[0] ?? null;
  const velocityLabel = formatVelocity(velocityItem);
  const latestRun = sourceRuns[0] ?? null;
  const firingAlertCount = observability?.alerts.filter((alert) => alert.firing).length ?? 0;

  const onSelectOperator = useCallback((operatorId: string) => {
    setSelectedOperatorId(operatorId);
    setSelectedSignalId(null);
  }, []);

  const onSelectSignal = useCallback((signal: Signal) => {
    setSelectedSignalId(signal.id);
    if (signal.related_operator_id) {
      setSelectedOperatorId(signal.related_operator_id);
    }
  }, []);

  const openOperator = useCallback(
    (operatorId: string) => {
      setSelectedOperatorId(operatorId);
      setSelectedSignalId(null);
      navigate(`/operators/${operatorId}`);
    },
    [navigate]
  );

  const goScreen = useCallback(
    (nextScreen: Screen) => {
      if (nextScreen === "operator") {
        const operatorId = selectedOperatorId ?? visibleOperators[0]?.id;
        navigate(operatorId ? `/operators/${operatorId}` : "/operators");
        return;
      }
      navigate(pathForScreen(nextScreen));
    },
    [navigate, selectedOperatorId, visibleOperators]
  );

  if (kioskMode) {
    return (
      <KioskMode
        operators={visibleOperators}
        heatmapCells={visibleHeatmapCells}
        signals={visibleSignals}
        selectedOperatorId={selectedOperatorId}
        onSelectOperator={setSelectedOperatorId}
      />
    );
  }

  return (
    <main className="wr-shell">
      <header className="wr-topbar">
        <div className="wr-brand">
          <span className="wr-logo" aria-hidden>
            <Hexagon size={25} />
            <i />
          </span>
          <div>
            <strong>Wellness Radar</strong>
            <span>METRO VANCOUVER</span>
          </div>
        </div>

        <nav className="wr-nav-tabs" aria-label="Screen navigation">
          {SCREEN_TABS.map((tab) => (
            <button
              key={tab.screen}
              className={screen === tab.screen ? "is-active" : ""}
              type="button"
              onClick={() => goScreen(tab.screen)}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        <div className="wr-topbar-spacer" />

        <button className="wr-global-search" type="button" onClick={() => navigate("/search")}>
          <Search size={14} />
          <span>Search ontology</span>
          <kbd>/</kbd>
        </button>
        <div className="wr-live">
          <span>
            <i />
            {loading ? "sync" : "live"}
          </span>
          <time>{formatClock(clock)}</time>
        </div>
      </header>

      <section className="wr-screen-area">
        {screen === "console" ? (
          <div className="wr-console">
            <div className="wr-console-main">
              <aside className="wr-console-rail">
                <section>
                  <h2>LAYERS</h2>
                  <div className="wr-layer-stack">
                    <LayerToggle
                      type="operator"
                      label="Operators"
                      count={visibleOperators.length}
                      on={layers.operators}
                      onToggle={() => setLayers((current) => ({ ...current, operators: !current.operators }))}
                    />
                    <LayerToggle
                      type="signal"
                      label="Signals"
                      count={visibleSignals.length}
                      on={layers.signals}
                      onToggle={() => setLayers((current) => ({ ...current, signals: !current.signals }))}
                    />
                    <LayerToggle
                      type="people"
                      label="People"
                      count={layers.people ? people.length : "off"}
                      on={layers.people}
                      onToggle={() => setLayers((current) => ({ ...current, people: !current.people }))}
                    />
                    <LayerToggle
                      type="opportunity"
                      label="Opportunity"
                      count={layers.opportunity ? "hexbin" : "off"}
                      on={layers.opportunity}
                      onToggle={() => setLayers((current) => ({ ...current, opportunity: !current.opportunity }))}
                    />
                  </div>
                </section>

                <section>
                  <h2>CATEGORY</h2>
                  <div className="wr-category-chips">
                    {CATEGORIES.map((item) => (
                      <button
                        key={item.value}
                        className={item.value === category ? "is-active" : ""}
                        type="button"
                        onClick={() => setCategory(item.value)}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                </section>

                <RangeSlider label="OPPORTUNITY >=" value={minOpportunity} onChange={setMinOpportunity} />
                <RangeSlider label="MIN CONFIDENCE" value={minConfidence} color="ok" onChange={setMinConfidence} />

                <VelocityCard velocity={velocityItem} />
                <FreshnessCard sources={sourceFreshness} latestRun={latestRun} firingAlertCount={firingAlertCount} />
              </aside>

              <div className="wr-console-map">
                <OperatorMap
                  operators={visibleOperators}
                  heatmapCells={visibleHeatmapCells}
                  signals={visibleSignals}
                  selectedOperatorId={selectedOperatorId}
                  selectedSignalId={selectedSignalId}
                  layers={layers}
                  onSelectOperator={onSelectOperator}
                  onSelectSignal={(signalId) => {
                    const signal = visibleSignals.find((item) => item.id === signalId);
                    if (signal) {
                      onSelectSignal(signal);
                    }
                  }}
                />
                <EntityDrawer
                  operator={selectedOperator}
                  signals={selectedOperatorSignals}
                  nearbyOperators={nearbyOperators}
                  supplyCount={supplyCount}
                  opportunityScore={opportunityScore}
                  velocityLabel={velocityLabel}
                  onClose={() => {
                    setSelectedOperatorId(null);
                    setSelectedSignalId(null);
                  }}
                  onOpenOperator={openOperator}
                />
              </div>
            </div>

            <SignalFeed
              loading={loading}
              error={error}
              signals={feedSignals}
              operators={visibleOperators}
              selectedOperatorId={selectedOperatorId}
              selectedSignalId={selectedSignalId}
              onSelectSignal={onSelectSignal}
              onClearSelection={() => {
                setSelectedOperatorId(null);
                setSelectedSignalId(null);
              }}
              onViewAll={() => navigate("/signals")}
            />
          </div>
        ) : screen === "operator" ? (
          <OperatorDetail
            operator={detailOperator}
            operators={detailOperators}
            signals={detailSignals}
            heatmapCells={heatmapCells}
            velocity={velocity}
            onBack={() => navigate("/")}
            onViewMap={(operatorId) => {
              setSelectedOperatorId(operatorId);
              setSelectedSignalId(null);
              navigate("/");
            }}
          />
        ) : screen === "feed" ? (
          <SignalFeed
            mode="screen"
            loading={loading}
            error={error}
            signals={sourceBackedSignals}
            operators={operators}
            selectedOperatorId={selectedOperatorId}
            selectedSignalId={selectedSignalId}
            minConfidence={minConfidence}
            trustFilter={trustFilter}
            signalTypeFilter={signalTypeFilter}
            onMinConfidenceChange={setMinConfidence}
            onTrustFilterChange={setTrustFilter}
            onSignalTypeFilterChange={setSignalTypeFilter}
            onSelectSignal={onSelectSignal}
            onClearSelection={() => {
              setSelectedOperatorId(null);
              setSelectedSignalId(null);
            }}
            onViewAll={() => undefined}
            onOpenOperator={openOperator}
          />
        ) : screen === "opportunity" ? (
          <div className="wr-opportunity-screen">
            <section className="wr-opportunity-map" aria-label="Opportunity hexbin map">
              <OperatorMap
                operators={[]}
                heatmapCells={visibleHeatmapCells}
                signals={[]}
                selectedOperatorId={null}
                layers={{ operators: false, signals: false, people: false, opportunity: true }}
                chrome={false}
                onSelectOperator={() => undefined}
              />
              <div className="wr-opportunity-title">
                <h1>Opportunity Surface</h1>
                <span>{sentenceCase(activeAnalyticsCategory(category))} / supply-demand whitespace</span>
              </div>
              <div className="wr-opportunity-categories" aria-label="Opportunity category">
                {CATEGORIES.filter((item) => item.value !== "all").slice(0, 5).map((item) => {
                  const active = item.value === activeAnalyticsCategory(category);
                  return (
                    <button
                      key={item.value}
                      className={active ? "is-active" : ""}
                      type="button"
                      onClick={() => setCategory(item.value)}
                    >
                      {item.label}
                    </button>
                  );
                })}
              </div>
              {visibleHeatmapCells[0] ? <OpportunityCallout cell={visibleHeatmapCells[0]} /> : null}
              <div className="wr-opportunity-legend">
                <span>OPPORTUNITY SCORE / H3 HEXBIN</span>
                <div>
                  <i />
                  <b>0 to 1</b>
                </div>
                <p>supply-demand signal, not guaranteed attractiveness</p>
              </div>
            </section>
            <OpportunityPanel
              scorecards={visibleScorecards}
              heatmapCells={visibleHeatmapCells}
              velocity={velocity}
              trends={trends}
            />
          </div>
        ) : screen === "people" ? (
          <div className="wr-people-screen">
            <PeopleGraph
              nodes={graphNodes}
              edges={graphEdges}
              selectedNodeId={selectedGraphNodeId}
              onSelectNode={setSelectedGraphNodeId}
            />
            <PeopleLeaderboard
              people={people}
              operators={operators}
              graphNodes={graphNodes}
              selectedNodeId={selectedGraphNodeId}
              onSelectNode={setSelectedGraphNodeId}
              onOpenOperator={openOperator}
            />
          </div>
        ) : screen === "search" ? (
          <SearchScreen
            operators={detailOperators}
            signals={sourceBackedSignals}
            people={people.filter((person) => person.source_refs.length > 0)}
            scorecards={scorecards.filter((scorecard) => scorecard.source_refs.length > 0)}
            onOpenOperator={openOperator}
            onOpenSignal={(signal) => {
              onSelectSignal(signal);
              navigate("/signals");
            }}
            onOpenPerson={(personId) => {
              const node = graphNodes.find((item) => item.entity_id === personId || item.id === personId);
              setSelectedGraphNodeId(node?.id ?? null);
              navigate("/people");
            }}
            onOpenOpportunity={() => navigate("/opportunity")}
          />
        ) : screen === "system" ? (
          <SystemScreen />
        ) : (
          <DeferredScreen
            screen={screen}
            operators={visibleOperators.length}
            signals={visibleSignals.length}
            people={people.length}
            scorecards={scorecards.length}
            trends={trends.length}
            graph={`${graphNodes.length}/${graphEdges.length}`}
          />
        )}
      </section>
    </main>
  );
}

function VelocityCard({ velocity }: { velocity: CategoryVelocity | null }) {
  const label = formatVelocity(velocity);
  const sparkValues = velocity
    ? [
        velocity.new_operator_count,
        velocity.job_velocity_count,
        velocity.event_velocity_count,
        velocity.news_velocity_count
      ]
    : [0, 1, 1, 2];

  return (
    <section className="wr-rail-card">
      <h2>CATEGORY VELOCITY / 90D</h2>
      <strong>{label}</strong>
      <Sparkline values={sparkValues} />
    </section>
  );
}

function FreshnessCard({
  sources,
  latestRun,
  firingAlertCount
}: {
  sources: SourceFreshness[];
  latestRun: SourceRun | null;
  firingAlertCount: number;
}) {
  const rows = sources.slice(0, 4);
  return (
    <section className="wr-rail-card">
      <h2>SOURCE FRESHNESS</h2>
      <div className="wr-freshness-list">
        {rows.map((source) => (
          <div key={source.source_name}>
            <i className={source.is_stale ? "is-stale" : ""} />
            <span>{source.source_name}</span>
            <strong>{source.age_hours === null ? "n/a" : formatAgeFromHours(source.age_hours)}</strong>
          </div>
        ))}
        {rows.length === 0 ? (
          <div>
            <i className={latestRun?.status === "success" ? "" : "is-stale"} />
            <span>{latestRun ? latestRun.source_name : "No source run"}</span>
            <strong>{latestRun?.status ?? "n/a"}</strong>
          </div>
        ) : null}
        {firingAlertCount > 0 ? (
          <div>
            <i className="is-stale" />
            <span>Ops alerts</span>
            <strong>{firingAlertCount}</strong>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function OpportunityCallout({ cell }: { cell: OpportunityHeatmapCell }) {
  return (
    <aside className="wr-opportunity-callout" aria-label="Hottest opportunity cell">
      <div>
        <strong>{cell.geo_name}</strong>
        <b>{formatScore(cell.opportunity_score)}</b>
      </div>
      <span>
        {cell.supply_count} operators / {formatPopulation(cell.population)} pop
        <br />
        demand &gt;&gt; supply
      </span>
    </aside>
  );
}

function Sparkline({ values }: { values: number[] }) {
  const width = 180;
  const height = 34;
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = Math.max(max - min, 1);
  const points = values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * width;
      const y = height - ((value - min) / range) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const area = `0,${height} ${points} ${width},${height}`;
  return (
    <svg className="wr-sparkline" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Velocity sparkline">
      <polygon points={area} />
      <polyline points={points} />
    </svg>
  );
}

function DeferredScreen({
  screen,
  operators,
  signals,
  people,
  scorecards,
  trends,
  graph
}: {
  screen: Screen;
  operators: number;
  signals: number;
  people: number;
  scorecards: number;
  trends: number;
  graph: string;
}) {
  const title = SCREEN_TABS.find((tab) => tab.screen === screen)?.label ?? "Screen";
  return (
    <div className="wr-deferred-screen">
      <span>DR2</span>
      <h1>{title}</h1>
      <p>This route is wired in the Luminous shell. Product UI for this screen is intentionally deferred to DR2.</p>
      <dl>
        <dt>operators</dt>
        <dd>{operators}</dd>
        <dt>signals</dt>
        <dd>{signals}</dd>
        <dt>people</dt>
        <dd>{people}</dd>
        <dt>scorecards</dt>
        <dd>{scorecards}</dd>
        <dt>trends</dt>
        <dd>{trends}</dd>
        <dt>graph</dt>
        <dd>{graph}</dd>
      </dl>
    </div>
  );
}

function routeFromPath(pathname: string): RouteState {
  const normalized = pathname.replace(/\/+$/, "") || "/";
  if (normalized === "/") {
    return { screen: "console", operatorId: null };
  }
  if (normalized.startsWith("/operators")) {
    const [, , operatorId] = normalized.split("/");
    return { screen: "operator", operatorId: operatorId ?? null };
  }
  if (normalized === "/signals") {
    return { screen: "feed", operatorId: null };
  }
  if (normalized === "/opportunity") {
    return { screen: "opportunity", operatorId: null };
  }
  if (normalized === "/people") {
    return { screen: "people", operatorId: null };
  }
  if (normalized === "/search") {
    return { screen: "search", operatorId: null };
  }
  if (normalized === "/system" || normalized === "/design-system") {
    return { screen: "system", operatorId: null };
  }
  return { screen: "console", operatorId: null };
}

function pathForScreen(screen: Screen): string {
  switch (screen) {
    case "console":
      return "/";
    case "operator":
      return "/operators";
    case "feed":
      return "/signals";
    case "opportunity":
      return "/opportunity";
    case "people":
      return "/people";
    case "search":
      return "/search";
    case "system":
      return "/system";
  }
}

function findOpportunityForOperator(
  operator: Operator,
  cells: OpportunityHeatmapCell[]
): OpportunityHeatmapCell | null {
  const candidates = [
    operator.neighborhood?.toLowerCase(),
    operator.municipality?.toLowerCase(),
    operator.address?.toLowerCase()
  ].filter(Boolean) as string[];
  return (
    cells.find((cell) => candidates.some((candidate) => cell.geo_name.toLowerCase().includes(candidate))) ??
    cells[0] ??
    null
  );
}

function hasCategoryOverlap(a: Operator, b: Operator): boolean {
  return a.categories.some((category) => b.categories.includes(category));
}

function formatVelocity(velocity: CategoryVelocity | null): string {
  if (!velocity) {
    return "n/a";
  }
  const numeric = Object.values(velocity.component_breakdown).find((value) => typeof value === "number") as
    | number
    | undefined;
  if (numeric !== undefined && numeric > 0 && numeric <= 1) {
    return `+${Math.round(numeric * 100)}%`;
  }
  const total =
    velocity.new_operator_count +
    velocity.job_velocity_count +
    velocity.event_velocity_count +
    velocity.news_velocity_count;
  return `+${total}`;
}

function activeAnalyticsCategory(category: string): string {
  return category === "all" ? "recovery_contrast_therapy" : category;
}

function formatPopulation(value: number | null): string {
  if (value === null) {
    return "n/a";
  }
  if (value >= 1000) {
    return `${Math.round(value / 1000)}k`;
  }
  return String(Math.round(value));
}

function formatClock(value: Date): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Vancouver",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short"
  }).format(value);
}
