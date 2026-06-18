import { X } from "lucide-react";
import { EntityBadge, ProvenanceBlock } from "../../components";
import type { Operator, Signal } from "../../lib/api";
import { formatAgeFromHours, formatScore, sentenceCase } from "../../lib/format";
import { colorForSignalType } from "../../lib/theme";

type Props = {
  operator: Operator | null;
  signals: Signal[];
  nearbyOperators: Operator[];
  supplyCount: number | null;
  opportunityScore: number | null;
  velocityLabel: string;
  onClose: () => void;
  onOpenOperator: (operatorId: string) => void;
};

export function EntityDrawer({
  operator,
  signals,
  nearbyOperators,
  supplyCount,
  opportunityScore,
  velocityLabel,
  onClose,
  onOpenOperator
}: Props) {
  if (!operator) {
    return null;
  }

  return (
    <aside className="wr-inspector" aria-label="Selected operator inspector">
      <button className="wr-inspector-close" type="button" onClick={onClose} title="Close inspector">
        <X size={16} />
      </button>
      <div className="wr-inspector-head">
        <div>
          <div className="wr-inspector-badges">
            <EntityBadge type="operator" label="OPERATOR" />
            <EntityBadge type="signal" label={operator.status} />
          </div>
          <h2>{operator.name}</h2>
          <p>
            {operator.neighborhood ?? operator.municipality ?? "Metro Vancouver"} /{" "}
            {operator.categories.slice(0, 2).map(sentenceCase).join(" / ")}
          </p>
        </div>
        <button className="wr-open-record" type="button" onClick={() => onOpenOperator(operator.id)}>
          OPEN
        </button>
      </div>

      <div className="wr-inspector-metrics">
        <MetricTile label="SUPPLY" value={supplyCount !== null ? String(supplyCount) : "n/a"} />
        <MetricTile
          label="OPP SCORE"
          value={opportunityScore !== null ? formatScore(opportunityScore) : "n/a"}
          tone="opportunity"
        />
        <MetricTile label="VELOCITY" value={velocityLabel} tone="signal" />
      </div>

      <ProvenanceBlock
        source_refs={operator.source_refs}
        confidence_score={operator.confidence_score}
        freshness_age_hours={operator.freshness_age_hours}
        compact
      />

      <section className="wr-related-signals">
        <h3>RELATED SIGNALS</h3>
        <div>
          {signals.slice(0, 4).map((signal) => (
            <article key={signal.id}>
              <span style={{ background: colorForSignalType(signal.type) }} />
              <div>
                <strong>{signal.title}</strong>
                <small>
                  {signal.source_name} / {formatAgeFromHours(signal.freshness_age_hours)}
                </small>
              </div>
            </article>
          ))}
          {signals.length === 0 ? <p>No related signals in current filters.</p> : null}
        </div>
      </section>

      <section className="wr-related-signals">
        <h3>NEARBY OPERATORS</h3>
        <div>
          {nearbyOperators.slice(0, 3).map((nearby) => (
            <article key={nearby.id}>
              <span />
              <div>
                <strong>{nearby.name}</strong>
                <small>{nearby.status} / same neighborhood</small>
              </div>
            </article>
          ))}
          {nearbyOperators.length === 0 ? <p>No same-area operators in the current view.</p> : null}
        </div>
      </section>
    </aside>
  );
}

function MetricTile({
  label,
  value,
  tone = "neutral"
}: {
  label: string;
  value: string;
  tone?: "neutral" | "opportunity" | "signal";
}) {
  return (
    <div className={`wr-inspector-metric wr-metric-${tone}`}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}
