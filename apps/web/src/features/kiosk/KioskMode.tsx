import { Radio } from "lucide-react";
import { OperatorMap } from "../map/OperatorMap";
import type { Operator, OpportunityHeatmapCell, Signal } from "../../lib/api";

type Props = {
  operators: Operator[];
  heatmapCells: OpportunityHeatmapCell[];
  signals: Signal[];
  selectedOperatorId: string | null;
  onSelectOperator: (operatorId: string) => void;
};

export function KioskMode({
  operators,
  heatmapCells,
  signals,
  selectedOperatorId,
  onSelectOperator
}: Props) {
  return (
    <main className="kioskShell">
      <OperatorMap
        operators={operators}
        heatmapCells={heatmapCells}
        selectedOperatorId={selectedOperatorId}
        onSelectOperator={onSelectOperator}
      />
      <aside className="kioskFeed" aria-label="Live signal feed">
        <div className="kioskHeader">
          <h1>Vancouver Wellness Radar</h1>
          <span>
            <Radio size={14} /> Live
          </span>
        </div>
        <div className="kioskSignalList">
          {signals.slice(0, 8).map((signal) => (
            <button
              key={signal.id}
              type="button"
              disabled={!signal.related_operator_id}
              onClick={() => signal.related_operator_id && onSelectOperator(signal.related_operator_id)}
            >
              <strong>{signal.title}</strong>
              <span>
                {signal.source_name} · {new Date(signal.occurred_at).toLocaleDateString()} ·{" "}
                {formatFreshness(signal.freshness_age_hours)}
              </span>
            </button>
          ))}
        </div>
      </aside>
    </main>
  );
}

function formatFreshness(ageHours?: number | null): string {
  if (ageHours === null || ageHours === undefined) {
    return "freshness n/a";
  }
  if (ageHours < 1) {
    return "<1h";
  }
  if (ageHours < 48) {
    return `${Math.round(ageHours)}h`;
  }
  return `${Math.round(ageHours / 24)}d`;
}
