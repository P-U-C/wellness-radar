import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { SourceFreshnessPanel } from "../features/admin/SourceFreshnessPanel";
import { EntityDrawer } from "../features/entities/EntityDrawer";
import { SignalFeed } from "../features/feed/SignalFeed";
import { OperatorMap } from "../features/map/OperatorMap";
import { PeopleLeaderboard } from "../features/people/PeopleLeaderboard";
import {
  fetchOperators,
  fetchPeople,
  fetchSignals,
  fetchSourceFreshness,
  fetchSourceRuns,
  type Operator,
  type Person,
  type Signal,
  type SourceFreshness,
  type SourceRun
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

export function App() {
  const [operators, setOperators] = useState<Operator[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [sourceRuns, setSourceRuns] = useState<SourceRun[]>([]);
  const [sourceFreshness, setSourceFreshness] = useState<SourceFreshness[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [selectedOperatorId, setSelectedOperatorId] = useState<string | null>(null);
  const [category, setCategory] = useState("all");
  const [peopleSort, setPeopleSort] = useState("confidence");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [operatorData, signalData, runData, freshnessData, peopleData] = await Promise.all([
        fetchOperators(category),
        fetchSignals(),
        fetchSourceRuns(),
        fetchSourceFreshness(),
        fetchPeople(peopleSort)
      ]);
      setOperators(operatorData);
      setSignals(signalData);
      setSourceRuns(runData);
      setSourceFreshness(freshnessData);
      setPeople(peopleData);
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
          <PeopleLeaderboard people={people} sort={peopleSort} onSortChange={setPeopleSort} />
        </aside>

        <OperatorMap
          operators={visibleOperators}
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
