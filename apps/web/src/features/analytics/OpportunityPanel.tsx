import { Activity, MapPinned } from "lucide-react";
import type { CategoryVelocity, OpportunityHeatmapCell, OpportunityScorecard } from "../../lib/api";

type Props = {
  scorecards: OpportunityScorecard[];
  heatmapCells: OpportunityHeatmapCell[];
  velocity: CategoryVelocity[];
};

const COMPONENTS = [
  "demand_proxy",
  "low_supply_density",
  "category_growth",
  "target_demo_fit",
  "transit_access",
  "event_community_activity",
  "source_confidence"
];

export function OpportunityPanel({ scorecards, heatmapCells, velocity }: Props) {
  const topCell = heatmapCells[0];
  return (
    <section className="sideSection" aria-label="Opportunity analytics">
      <div className="sectionHeader">
        <h2>Opportunity</h2>
        <span>{scorecards.length}</span>
      </div>
      {topCell ? (
        <div className="metricBand compactMetric">
          <span>{topCell.geo_name}</span>
          <strong>{Math.round(topCell.opportunity_score * 100)}</strong>
          <small>{topCell.supply_count} operators traced to {topCell.source_refs.length} refs</small>
        </div>
      ) : null}
      <div className="scorecardList">
        {scorecards.slice(0, 3).map((scorecard) => (
          <article className="scorecard" key={scorecard.id}>
            <div className="scorecardTop">
              <strong>{scorecard.geo_name}</strong>
              <span>{Math.round(scorecard.opportunity_score * 100)}</span>
            </div>
            <div className="componentGrid">
              {COMPONENTS.map((component) => (
                <span key={component}>
                  {component.replaceAll("_", " ")}
                  <b>{formatComponent(scorecard.component_breakdown[component])}</b>
                </span>
              ))}
            </div>
            <small>{scorecard.caveat}</small>
            <small>
              {scorecard.source_refs.length} refs · {formatFreshness(scorecard.freshness_age_hours)}
            </small>
          </article>
        ))}
      </div>
      <div className="velocityGrid">
        {velocity.map((item) => (
          <div className="velocityCell" key={item.id}>
            <Activity size={13} />
            <span>{item.window_days}d</span>
            <strong>
              {item.new_operator_count}/{item.news_velocity_count}/{item.event_velocity_count}
            </strong>
          </div>
        ))}
      </div>
      {scorecards.length === 0 ? (
        <p className="emptyInline">
          <MapPinned size={14} /> Run M3 analytics to populate scorecards.
        </p>
      ) : null}
    </section>
  );
}

function formatComponent(value: unknown): string {
  if (typeof value !== "number") {
    return "-";
  }
  return `${Math.round(value * 100)}`;
}

function formatFreshness(ageHours?: number | null): string {
  if (ageHours === null || ageHours === undefined) {
    return "freshness n/a";
  }
  if (ageHours < 1) {
    return "updated <1h";
  }
  if (ageHours < 48) {
    return `updated ${Math.round(ageHours)}h`;
  }
  return `updated ${Math.round(ageHours / 24)}d`;
}
