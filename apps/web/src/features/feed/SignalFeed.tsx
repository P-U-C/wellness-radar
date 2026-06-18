import { AlertCircle } from "lucide-react";
import type { CSSProperties } from "react";
import { EntityBadge, ProvenanceBlock, RangeSlider, SignalCard } from "../../components";
import type { Operator, Signal } from "../../lib/api";
import { sentenceCase } from "../../lib/format";
import { colorForSignalType, colorForTrustTier } from "../../lib/theme";

type Props = {
  loading: boolean;
  error: string | null;
  signals: Signal[];
  operators?: Operator[];
  selectedOperatorId: string | null;
  selectedSignalId: string | null;
  mode?: "strip" | "screen";
  minConfidence?: number;
  trustFilter?: string;
  signalTypeFilter?: string;
  onMinConfidenceChange?: (value: number) => void;
  onTrustFilterChange?: (tier: string) => void;
  onSignalTypeFilterChange?: (type: string) => void;
  onSelectSignal: (signal: Signal) => void;
  onClearSelection: () => void;
  onViewAll: () => void;
  onOpenOperator?: (operatorId: string) => void;
};

export function SignalFeed({
  loading,
  error,
  signals,
  operators = [],
  selectedOperatorId,
  selectedSignalId,
  mode = "strip",
  minConfidence = 0,
  trustFilter = "all",
  signalTypeFilter = "all",
  onMinConfidenceChange,
  onTrustFilterChange,
  onSignalTypeFilterChange,
  onSelectSignal,
  onClearSelection,
  onViewAll,
  onOpenOperator
}: Props) {
  if (mode === "screen") {
    return (
      <SignalFeedScreen
        loading={loading}
        error={error}
        signals={signals}
        operators={operators}
        selectedSignalId={selectedSignalId}
        minConfidence={minConfidence}
        trustFilter={trustFilter}
        signalTypeFilter={signalTypeFilter}
        onMinConfidenceChange={onMinConfidenceChange}
        onTrustFilterChange={onTrustFilterChange}
        onSignalTypeFilterChange={onSignalTypeFilterChange}
        onSelectSignal={onSelectSignal}
        onOpenOperator={onOpenOperator}
      />
    );
  }

  const visibleSignals = signals.slice(0, 6);
  const earlierCount = Math.max(0, signals.length - visibleSignals.length);

  return (
    <aside className="wr-feed-strip" aria-label="Signal feed">
      <div className="wr-feed-head">
        <span>SIGNAL FEED / LAST 24H</span>
        <button type="button" onClick={onViewAll}>
          view all
        </button>
        {selectedOperatorId ? (
          <button type="button" onClick={onClearSelection}>
            clear focus
          </button>
        ) : null}
        <i />
        <b>now</b>
      </div>
      {loading ? <p className="wr-feed-state">Loading source-backed signals...</p> : null}
      {error ? (
        <p className="wr-feed-state is-error">
          <AlertCircle size={15} /> {error}
        </p>
      ) : null}
      {!loading && !error && signals.length === 0 ? (
        <p className="wr-feed-state">No source-backed signals match the current filters.</p>
      ) : null}
      {!loading && !error && signals.length > 0 ? (
        <div className="wr-feed-row">
          {visibleSignals.map((signal) => (
            <SignalCard
              key={signal.id}
              signal={signal}
              context={contextForSignal(signal, operators)}
              selected={signal.id === selectedSignalId}
              variant="strip"
              onSelect={onSelectSignal}
            />
          ))}
          <div className="wr-feed-more">
            +{earlierCount}
            <br />
            earlier
          </div>
        </div>
      ) : null}
    </aside>
  );
}

type SignalFeedScreenProps = {
  loading: boolean;
  error: string | null;
  signals: Signal[];
  operators: Operator[];
  selectedSignalId: string | null;
  minConfidence: number;
  trustFilter: string;
  signalTypeFilter: string;
  onMinConfidenceChange?: (value: number) => void;
  onTrustFilterChange?: (tier: string) => void;
  onSignalTypeFilterChange?: (type: string) => void;
  onSelectSignal: (signal: Signal) => void;
  onOpenOperator?: (operatorId: string) => void;
};

const SIGNAL_TYPE_FILTERS = [
  { key: "new_operator", label: "New operator" },
  { key: "press", label: "Press / news" },
  { key: "whitespace", label: "Whitespace" },
  { key: "recall", label: "Regulatory / recall" },
  { key: "osm_observation", label: "OSM observation" }
];

const TRUST_TIERS = [
  "official",
  "reputable_press",
  "commercial_api",
  "community",
  "informal",
  "ai_inferred"
];

function SignalFeedScreen({
  loading,
  error,
  signals,
  operators,
  selectedSignalId,
  minConfidence,
  trustFilter,
  signalTypeFilter,
  onMinConfidenceChange,
  onTrustFilterChange,
  onSignalTypeFilterChange,
  onSelectSignal,
  onOpenOperator
}: SignalFeedScreenProps) {
  const filteredSignals = signals
    .filter((signal) => signal.confidence_score >= minConfidence)
    .filter((signal) => trustFilter === "all" || signal.trust_tier === trustFilter)
    .filter((signal) => signalTypeFilter === "all" || matchesSignalType(signal.type, signalTypeFilter))
    .sort((a, b) => Date.parse(b.occurred_at) - Date.parse(a.occurred_at));
  const selectedSignal =
    filteredSignals.find((signal) => signal.id === selectedSignalId) ?? filteredSignals[0] ?? null;
  const selectedOperator = selectedSignal?.related_operator_id
    ? operators.find((operator) => operator.id === selectedSignal.related_operator_id) ?? null
    : null;
  const groupedSignals = groupSignalsByDay(filteredSignals);

  return (
    <div className="wr-signals-screen">
      <aside className="wr-signals-filter" aria-label="Signal filters">
        <section>
          <h2>SIGNAL TYPE</h2>
          <div className="wr-filter-stack">
            {SIGNAL_TYPE_FILTERS.map((item) => {
              const count = signals.filter((signal) => matchesSignalType(signal.type, item.key)).length;
              const active = signalTypeFilter === item.key;
              const color = colorForSignalType(item.key);
              return (
                <button
                  key={item.key}
                  className={active ? "is-active" : ""}
                  type="button"
                  style={{ "--wr-filter-color": color } as CSSProperties}
                  onClick={() => onSignalTypeFilterChange?.(active ? "all" : item.key)}
                >
                  <i />
                  <span>{item.label}</span>
                  <b>{count}</b>
                </button>
              );
            })}
          </div>
        </section>

        <section>
          <h2>TRUST TIER</h2>
          <div className="wr-tier-list">
            {TRUST_TIERS.map((tier) => {
              const active = trustFilter === tier;
              const count = signals.filter((signal) => signal.trust_tier === tier).length;
              return (
                <button
                  key={tier}
                  className={active ? "is-active" : ""}
                  type="button"
                  onClick={() => onTrustFilterChange?.(active ? "all" : tier)}
                >
                  <i style={{ background: colorForTrustTier(tier) }} />
                  <span>{sentenceCase(tier)}</span>
                  <b>{count}</b>
                </button>
              );
            })}
          </div>
        </section>

        <RangeSlider
          label="CONFIDENCE >="
          value={minConfidence}
          color="ok"
          onChange={onMinConfidenceChange ?? (() => undefined)}
        />
      </aside>

      <section className="wr-signal-stream" aria-label="Reverse chronological signal stream">
        <header className="wr-signals-stream-head">
          <div>
            <h1>Signal Feed</h1>
            <span>{filteredSignals.length} signals / last 24h / reverse chronological</span>
          </div>
          <span>
            sort <b>newest</b>
          </span>
        </header>

        <div className="wr-signals-stream-body">
          {loading ? <p className="wr-feed-state">Loading source-backed signals...</p> : null}
          {error ? (
            <p className="wr-feed-state is-error">
              <AlertCircle size={15} /> {error}
            </p>
          ) : null}
          {!loading && !error && filteredSignals.length === 0 ? (
            <p className="wr-feed-state">No source-backed signals match the current filters.</p>
          ) : null}
          {!loading && !error
            ? groupedSignals.map((group) => (
                <section className="wr-day-group" key={group.label}>
                  <div className="wr-day-divider">
                    <span>{group.label}</span>
                    <i />
                  </div>
                  {group.signals.map((signal) => (
                    <SignalCard
                      key={signal.id}
                      signal={signal}
                      selected={signal.id === selectedSignal?.id}
                      variant="stream"
                      context={contextForSignal(signal, operators)}
                      actionLabel={signal.lat !== null && signal.lng !== null ? "fly to" : undefined}
                      onSelect={onSelectSignal}
                    />
                  ))}
                </section>
              ))
            : null}
        </div>
      </section>

      <aside className="wr-signal-detail" aria-label="Signal detail">
        {selectedSignal ? (
          <>
            <h2>SIGNAL DETAIL</h2>
            <EntityBadge type="signal" label={selectedSignal.type || selectedSignal.severity} />
            <h3>{selectedSignal.title}</h3>
            <p>{selectedSignal.summary ?? selectedSignal.why_it_matters ?? "No source summary provided."}</p>
            <ProvenanceBlock
              source_refs={selectedSignal.source_refs}
              confidence_score={selectedSignal.confidence_score}
              freshness_age_hours={selectedSignal.freshness_age_hours}
              compact
            />
            <section className="wr-ai-card">
              <h4>AI ENRICHMENT</h4>
              <p>
                {selectedSignal.why_it_matters ?? "No generated why-it-matters note on this signal."}{" "}
                <span>Enrichment, not a source of truth.</span>
              </p>
              <dl>
                <dt>model</dt>
                <dd>{selectedSignal.ai_model ?? "n/a"}</dd>
                <dt>prompt</dt>
                <dd>{selectedSignal.prompt_version ?? "n/a"}</dd>
              </dl>
            </section>
            {selectedOperator ? (
              <button
                className="wr-primary-action"
                type="button"
                onClick={() => onOpenOperator?.(selectedOperator.id)}
              >
                Open operator record
              </button>
            ) : (
              <span className="wr-muted">No linked operator record.</span>
            )}
          </>
        ) : (
          <p className="wr-feed-state">Select a signal to inspect its provenance.</p>
        )}
      </aside>
    </div>
  );
}

function matchesSignalType(type: string, filter: string): boolean {
  if (filter === "all") {
    return true;
  }
  const normalized = type.toLowerCase();
  if (filter === "new_operator") {
    return normalized.includes("new_operator") || normalized.includes("opening") || normalized.includes("permit");
  }
  if (filter === "press") {
    return normalized.includes("press") || normalized.includes("news");
  }
  if (filter === "whitespace") {
    return normalized.includes("whitespace") || normalized.includes("opportunity");
  }
  if (filter === "recall") {
    return normalized.includes("recall") || normalized.includes("regulatory");
  }
  return normalized.includes(filter);
}

function contextForSignal(signal: Signal, operators: Operator[]): string | null {
  const operator = signal.related_operator_id
    ? operators.find((item) => item.id === signal.related_operator_id) ?? null
    : null;
  return operator?.neighborhood ?? operator?.municipality ?? null;
}

function groupSignalsByDay(signals: Signal[]): Array<{ label: string; signals: Signal[] }> {
  const groups = new Map<string, Signal[]>();
  for (const signal of signals) {
    const label = dayLabel(signal.occurred_at);
    groups.set(label, [...(groups.get(label) ?? []), signal]);
  }
  return Array.from(groups.entries()).map(([label, items]) => ({ label, signals: items }));
}

function dayLabel(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "UNDATED";
  }
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  if (sameDay(date, today)) {
    return "TODAY";
  }
  if (sameDay(date, yesterday)) {
    return "YESTERDAY";
  }
  return new Intl.DateTimeFormat("en-CA", { month: "short", day: "2-digit" }).format(date).toUpperCase();
}

function sameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}
