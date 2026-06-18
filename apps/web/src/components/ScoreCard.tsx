import type { OpportunityScorecard } from "../lib/api";
import { formatAgeFromHours, formatScore, sentenceCase } from "../lib/format";
import { magma } from "../lib/theme";
import { ConfidenceBar } from "./ConfidenceBar";
import { SourceChip } from "./SourceChip";

type Props = {
  scorecard: OpportunityScorecard;
  rank: number;
};

export function ScoreCard({ scorecard, rank }: Props) {
  const components = Object.entries(scorecard.component_breakdown)
    .filter(([, value]) => typeof value === "number")
    .slice(0, 4) as Array<[string, number]>;
  const source = scorecard.source_refs[0];
  const scoreColor = magma(scorecard.opportunity_score);

  return (
    <article className="wr-score-card">
      <div className="wr-score-head">
        <span>{String(rank).padStart(2, "0")}</span>
        <strong>{scorecard.geo_name}</strong>
        <b style={{ color: scoreColor }}>{formatScore(scorecard.opportunity_score)}</b>
      </div>
      <div className="wr-score-stats">
        <span>
          Level
          <strong>{scorecard.geo_code}</strong>
        </span>
        <span>
          Method
          <strong>{scorecard.calculation_method}</strong>
        </span>
        <span>
          Fresh
          <strong>{formatAgeFromHours(scorecard.freshness_age_hours)}</strong>
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
        <span>{formatAgeFromHours(scorecard.freshness_age_hours)}</span>
      </div>
      <ConfidenceBar score={scorecard.confidence_score} />
    </article>
  );
}
