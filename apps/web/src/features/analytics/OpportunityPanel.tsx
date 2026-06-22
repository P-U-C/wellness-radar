import { AlertTriangle } from "lucide-react";
import { ConfidenceBar, ScoreCard, SourceChip } from "../../components";
import type {
  CategoryVelocity,
  Operator,
  OpportunityHeatmapCell,
  OpportunityProposition,
  OpportunityScorecard,
  TrendTile
} from "../../lib/api";
import { formatScore } from "../../lib/format";

type Props = {
  scorecards: OpportunityScorecard[];
  heatmapCells: OpportunityHeatmapCell[];
  propositions: OpportunityProposition[];
  velocity: CategoryVelocity[];
  operators: Operator[];
  trends?: TrendTile[];
};

export function OpportunityPanel({
  scorecards,
  heatmapCells,
  propositions,
  velocity,
  operators,
  trends = []
}: Props) {
  const rankedScorecards = [...scorecards].sort((a, b) => b.opportunity_score - a.opportunity_score);
  const rankedPropositions = [...propositions].sort((a, b) => b.opportunity_score - a.opportunity_score);
  const reachableCount = operators.filter((operator) => (operator.contacts ?? []).length > 0).length;
  const fixtureBacked = trends.some((trend) => trend.is_stub);
  const level = heatmapCells[0]?.geo_level ?? "CSD";
  const method =
    rankedScorecards[0]?.calculation_method ??
    heatmapCells[0]?.calculation_method ??
    "undersupply x demand growth x access gap";
  const velocityTotal = velocity.reduce(
    (sum, item) =>
      sum +
      item.new_operator_count +
      item.job_velocity_count +
      item.event_velocity_count +
      item.news_velocity_count,
    0
  );

  return (
    <aside className="wr-opportunity-panel" aria-label="Ranked opportunities">
      <div className="wr-opportunity-panel-head">
        <strong>Ranked opportunities</strong>
        <span>
          {rankedScorecards.length || heatmapCells.length} areas / {rankedPropositions.length} propositions /{" "}
          {level}
        </span>
      </div>

      <div className="wr-scorecard-list">
        {rankedPropositions.length > 0 ? (
          <section className="wr-proposition-stack" aria-label="Written propositions">
            {rankedPropositions.slice(0, 5).map((proposition) => (
              <PropositionCard key={proposition.id} proposition={proposition} />
            ))}
          </section>
        ) : null}
        {rankedScorecards.slice(0, 12).map((scorecard, index) => (
          <ScoreCard
            key={scorecard.id}
            scorecard={scorecard}
            heatmapCell={findCell(scorecard, heatmapCells)}
            rank={index + 1}
            highlighted={index === 0}
          />
        ))}
        {rankedScorecards.length === 0 ? (
          <p className="wr-feed-state">No opportunity scorecards are available for this category.</p>
        ) : null}
      </div>

      <footer className="wr-opportunity-method">
        <p>
          Method: {method}. Velocity inputs currently total {velocityTotal} observed source-backed events. Scores are
          supply-demand signals, not guaranteed attractiveness. Reachable operators: {reachableCount}.
        </p>
        <span className={fixtureBacked ? "is-fixture" : ""}>
          {fixtureBacked ? <AlertTriangle size={13} /> : null}
          peer-city inputs {fixtureBacked ? "fixture-backed" : "source-backed"} / top score{" "}
          {rankedScorecards[0] ? formatScore(rankedScorecards[0].opportunity_score) : "n/a"}
        </span>
      </footer>
    </aside>
  );
}

function PropositionCard({ proposition }: { proposition: OpportunityProposition }) {
  const source = proposition.source_refs[0];
  const demandStatus = demandStatusFor(proposition);
  return (
    <article className="wr-proposition-card">
      <header>
        <strong>{proposition.headline}</strong>
        <b>{formatScore(proposition.opportunity_score)}</b>
      </header>
      <p>{proposition.summary}</p>
      <div className="wr-proposition-evidence">
        <span>
          Competitors
          <strong>
            {proposition.competitor_count_within_radius} / {formatRadius(proposition.competitor_radius_km)}
          </strong>
        </span>
        <span>
          Population
          <strong>{formatPopulation(proposition.population)}</strong>
        </span>
        <span>
          Demand
          <strong>{demandStatus.replaceAll("_", " ")}</strong>
        </span>
      </div>
      {proposition.supporting_signals.length > 0 ? (
        <ul className="wr-proposition-signals">
          {proposition.supporting_signals.slice(0, 3).map((signal) => (
            <li key={`${signal.kind}-${signal.label}`}>{signal.label}</li>
          ))}
        </ul>
      ) : null}
      <footer>
        {source ? <SourceChip refData={source} compact /> : <span className="wr-muted">No source</span>}
        <span>{proposition.geo_level}</span>
      </footer>
      <ConfidenceBar score={proposition.confidence_score} />
    </article>
  );
}

function demandStatusFor(proposition: OpportunityProposition): string {
  const inputs = proposition.component_breakdown.inputs;
  if (inputs && typeof inputs === "object" && "demand_source_status" in inputs) {
    return String(inputs.demand_source_status);
  }
  return proposition.demand_source;
}

function formatRadius(value: number): string {
  return `${Number.isInteger(value) ? value.toFixed(0) : value.toFixed(1)}km`;
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

function findCell(
  scorecard: OpportunityScorecard,
  heatmapCells: OpportunityHeatmapCell[]
): OpportunityHeatmapCell | null {
  return (
    heatmapCells.find((cell) => cell.geo_code === scorecard.geo_code) ??
    heatmapCells.find((cell) => cell.geo_name.toLowerCase() === scorecard.geo_name.toLowerCase()) ??
    heatmapCells.find((cell) => cell.geo_name.toLowerCase().includes(scorecard.geo_name.toLowerCase())) ??
    null
  );
}
