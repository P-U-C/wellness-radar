import { Monitor, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { SourceFreshnessPanel } from "../features/admin/SourceFreshnessPanel";
import { OpportunityPanel } from "../features/analytics/OpportunityPanel";
import { TrendTiles } from "../features/analytics/TrendTiles";
import { EntityDrawer } from "../features/entities/EntityDrawer";
import { SignalFeed } from "../features/feed/SignalFeed";
import { PeopleGraph } from "../features/graph/PeopleGraph";
import { KioskMode } from "../features/kiosk/KioskMode";
import { OperatorMap } from "../features/map/OperatorMap";
import { PeopleLeaderboard } from "../features/people/PeopleLeaderboard";
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
  const [category, setCategory] = useState("all");
  const [peopleSort, setPeopleSort] = useState("influence");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  const visibleOperators = useMemo(
    () =>
      operators.filter(
        (operator) =>
          operator.source_refs.length > 0 &&
          isInBcBounds(operator.lat, operator.lng) &&
          (category === "all" || operator.categories.includes(category))
      ),
    [operators, category]
  );

  const visibleSignals = useMemo(() => {
    const operatorIds = new Set(visibleOperators.map((operator) => operator.id));
    return signals
      .filter((signal) => signal.source_refs.length > 0)
      .filter((signal) => !signal.related_operator_id || operatorIds.has(signal.related_operator_id))
      .sort((a, b) => Date.parse(b.occurred_at) - Date.parse(a.occurred_at));
  }, [signals, visibleOperators]);

  const feedSignals = useMemo(() => {
    if (!selectedOperatorId) {
      return visibleSignals;
    }
    return visibleSignals.filter(
      (signal) => !signal.related_operator_id || signal.related_operator_id === selectedOperatorId
    );
  }, [selectedOperatorId, visibleSignals]);

  const selectedOperator = visibleOperators.find((operator) => operator.id === selectedOperatorId) ?? null;
  const latestRun = sourceRuns[0];
  const firingAlertCount = observability?.alerts.filter((alert) => alert.firing).length ?? null;

  if (kioskMode) {
    return (
      <KioskMode
        operators={visibleOperators}
        heatmapCells={heatmapCells}
        signals={visibleSignals}
        selectedOperatorId={selectedOperatorId}
        onSelectOperator={setSelectedOperatorId}
      />
    );
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <h1>Vancouver Wellness Radar</h1>
          <span className="subtle">MVP private alpha</span>
        </div>
        <div className="topbarControls">
          <select
            aria-label="Category"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          >
            {CATEGORIES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
          <span className="freshness">
            {latestRun ? `${latestRun.source_name}: ${latestRun.status}` : "No source run yet"}
          </span>
          {firingAlertCount !== null ? (
            <span className="freshness">{firingAlertCount} ops alerts</span>
          ) : null}
          <a className="iconButton" href="?mode=kiosk" title="Open kiosk mode">
            <Monitor size={16} />
            <span>Kiosk</span>
          </a>
          <button className="iconButton" type="button" onClick={() => void loadData()} title="Refresh">
            <RefreshCw size={16} />
            <span>Refresh</span>
          </button>
        </div>
      </header>

      <section className="workspace">
        <aside className="leftRail">
          <h2>Categories</h2>
          <div className="chips">
            {CATEGORIES.map((item) => (
              <button
                className={item.value === category ? "chip active" : "chip"}
                key={item.value}
                type="button"
                onClick={() => setCategory(item.value)}
              >
                {item.label}
              </button>
            ))}
          </div>
          <div className="metricBand">
            <span>Operators</span>
            <strong>{visibleOperators.length}</strong>
          </div>
          <div className="metricBand">
            <span>Signals</span>
            <strong>{visibleSignals.length}</strong>
          </div>
          <div className="sourceBox">
            <span>Source</span>
            <strong>M2 sources enabled</strong>
            <small>OSM, OrgBook, RSS, official feeds, manual seeds, and governed people import.</small>
          </div>
          <SourceFreshnessPanel sources={sourceFreshness} />
          <OpportunityPanel scorecards={scorecards} heatmapCells={heatmapCells} velocity={velocity} />
          <TrendTiles trends={trends} />
          <PeopleLeaderboard people={people} sort={peopleSort} onSortChange={setPeopleSort} />
          <PeopleGraph nodes={graphNodes} edges={graphEdges} />
        </aside>

        <OperatorMap
          operators={visibleOperators}
          heatmapCells={heatmapCells}
          selectedOperatorId={selectedOperatorId}
          onSelectOperator={setSelectedOperatorId}
        />

        <SignalFeed
          loading={loading}
          error={error}
          signals={feedSignals}
          selectedOperatorId={selectedOperatorId}
          onSelectOperator={setSelectedOperatorId}
          onClearSelection={() => setSelectedOperatorId(null)}
        />
      </section>

      <EntityDrawer
        operator={selectedOperator}
        signals={visibleSignals.filter((signal) => signal.related_operator_id === selectedOperator?.id)}
        nearbyOperators={visibleOperators.filter(
          (operator) =>
            selectedOperator &&
            operator.id !== selectedOperator.id &&
            operator.neighborhood === selectedOperator.neighborhood
        )}
        onClose={() => setSelectedOperatorId(null)}
      />
    </main>
  );
}
