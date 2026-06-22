import { AlertTriangle } from "lucide-react";
import { ScoreCard } from "../../components";
import type { CategoryVelocity, Operator, OpportunityHeatmapCell, OpportunityScorecard, TrendTile } from "../../lib/api";
import { formatScore } from "../../lib/format";

type Props = {
  scorecards: OpportunityScorecard[];
  heatmapCells: OpportunityHeatmapCell[];
  velocity: CategoryVelocity[];
  operators: Operator[];
  trends?: TrendTile[];
};

export function OpportunityPanel({ scorecards, heatmapCells, velocity, operators, trends = [] }: Props) {
  const rankedScorecards = [...scorecards].sort((a, b) => b.opportunity_score - a.opportunity_score);
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
          {rankedScorecards.length || heatmapCells.length} areas / {reachableCount} reachable / {level} level
        </span>
      </div>

      <div className="wr-scorecard-list">
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
          supply-demand signals, not guaranteed attractiveness.
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
