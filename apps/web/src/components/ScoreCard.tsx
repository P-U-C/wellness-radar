import type { OpportunityHeatmapCell, OpportunityScorecard } from "../lib/api";
import { formatAgeFromHours, formatScore, sentenceCase } from "../lib/format";
import { magma } from "../lib/theme";
import { ConfidenceBar } from "./ConfidenceBar";
import { SourceChip } from "./SourceChip";

type Props = {
  scorecard: OpportunityScorecard;
  heatmapCell?: OpportunityHeatmapCell | null;
  rank: number;
  highlighted?: boolean;
};

export function ScoreCard({ scorecard, heatmapCell = null, rank, highlighted = false }: Props) {
  const components = selectComponents(scorecard.component_breakdown)
    .filter(([, value]) => typeof value === "number")
    .slice(0, 3) as Array<[string, number]>;
  const source = scorecard.source_refs[0];
  const scoreColor = magma(scorecard.opportunity_score);

  return (
    <article className={`wr-score-card${highlighted ? " is-highlighted" : ""}`}>
      <div className="wr-score-head">
        <span>{String(rank).padStart(2, "0")}</span>
        <strong>{scorecard.geo_name}</strong>
        <b style={{ color: scoreColor }}>{formatScore(scorecard.opportunity_score)}</b>
      </div>
      <div className="wr-score-stats">
        <span>
          Supply
          <strong>{heatmapCell ? String(heatmapCell.supply_count) : "n/a"}</strong>
        </span>
        <span>
          Pop
          <strong>{formatPopulation(heatmapCell?.population)}</strong>
        </span>
        <span>
          Demand delta
          <strong>{formatDemandDelta(scorecard.component_breakdown)}</strong>
        </span>
      </div>
      {components.length > 0 ? (
        <div className="wr-score-components">
          <span>COMPONENT BREAKDOWN</span>
          {components.map(([key, value]) => (
            <div className="wr-score-component" key={key}>
              <span>{sentenceCase(key)}</span>
              <div aria-hidden>
                <i style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%`, background: magma(value) }} />
              </div>
              <strong>{formatScore(value)}</strong>
            </div>
          ))}
        </div>
      ) : null}
      <div className="wr-score-foot">
        {source ? <SourceChip refData={source} compact /> : <span className="wr-muted">No source</span>}
        <span>verified {formatAgeFromHours(scorecard.freshness_age_hours)}</span>
      </div>
      <ConfidenceBar score={scorecard.confidence_score} />
    </article>
  );
}

function selectComponents(components: Record<string, unknown>): Array<[string, unknown]> {
  const aliases = [
    ["undersupply", ["undersupply", "low_supply_density", "supply_gap"]],
    ["demand grow", ["demand_growth", "category_growth", "demand_proxy"]],
    ["access gap", ["access_gap", "transit_access", "target_demo_fit"]]
  ] as const;
  const selected: Array<[string, unknown]> = [];
  for (const [label, keys] of aliases) {
    const key = keys.find((candidate) => typeof components[candidate] === "number");
    if (key) {
      selected.push([label, components[key]]);
    }
  }
  if (selected.length >= 3) {
    return selected;
  }
  for (const [key, value] of Object.entries(components)) {
    if (typeof value === "number" && !selected.some(([label]) => label === key)) {
      selected.push([key, value]);
    }
  }
  return selected;
}

function formatPopulation(value?: number | null): string {
  if (value === null || value === undefined) {
    return "n/a";
  }
  if (value >= 1000) {
    return `${Math.round(value / 1000)}k`;
  }
  return String(Math.round(value));
}

function formatDemandDelta(components: Record<string, unknown>): string {
  const value =
    numericComponent(components.category_growth) ??
    numericComponent(components.demand_growth) ??
    numericComponent(components.demand_proxy);
  if (value === null) {
    return "n/a";
  }
  return value <= 1 ? `+${Math.round(value * 100)}%` : `+${Math.round(value)}`;
}

function numericComponent(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}
