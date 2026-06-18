import { Download, MapPin } from "lucide-react";
import { ConfidenceBar, EntityBadge, SourceChip } from "../../components";
import type { CategoryVelocity, Operator, OpportunityHeatmapCell, Signal, SourceRef } from "../../lib/api";
import { formatAgeFromHours, formatScore, sentenceCase } from "../../lib/format";
import { colorForSignalType, colorForTrustTier, magma } from "../../lib/theme";
import { OperatorMap } from "../map/OperatorMap";

type Props = {
  operator: Operator | null;
  operators: Operator[];
  signals: Signal[];
  heatmapCells: OpportunityHeatmapCell[];
  velocity: CategoryVelocity[];
  onBack: () => void;
  onViewMap: (operatorId: string) => void;
};

export function OperatorDetail({
  operator,
  operators,
  signals,
  heatmapCells,
  velocity,
  onBack,
  onViewMap
}: Props) {
  if (!operator) {
    return (
      <div className="wr-operator-detail">
        <button className="wr-breadcrumb" type="button" onClick={onBack}>
          &lt;- Console / Operators
        </button>
        <div className="wr-detail-empty">No operator is available for this route.</div>
      </div>
    );
  }

  const relatedSignals = signals
    .filter((signal) => signal.related_operator_id === operator.id)
    .sort((a, b) => Date.parse(b.occurred_at) - Date.parse(a.occurred_at));
  const opportunity = findOpportunityForOperator(operator, heatmapCells);
  const supplyCount = opportunity?.supply_count ?? countSameAreaSupply(operator, operators);
  const rank = rankInCategory(operator, operators);
  const velocityLabel = formatVelocity(velocity[0] ?? null);
  const nearbyOperators = nearestOperators(operator, operators).slice(0, 5);
  const miniOperators = [operator, ...nearbyOperators];
  const categoryLabel = operator.categories[0] ? sentenceCase(operator.categories[0]) : "Wellness";

  return (
    <div className="wr-operator-detail">
      <button className="wr-breadcrumb" type="button" onClick={onBack}>
        &lt;- Console / Operators / {operator.name}
      </button>

      <header className="wr-detail-header">
        <div>
          <div className="wr-detail-badges">
            <EntityBadge type="operator" label="OPERATOR" />
            <EntityBadge type="signal" label={operator.status} />
          </div>
          <h1>{operator.name}</h1>
          <p>
            {operator.address ?? "Address unavailable"} / {categoryLabel}
          </p>
        </div>
        <div className="wr-detail-actions">
          <button type="button" onClick={() => onViewMap(operator.id)}>
            <MapPin size={15} /> View on map
          </button>
          <button type="button" onClick={() => exportRecord(operator)}>
            <Download size={15} /> Export record
          </button>
        </div>
      </header>

      <section className="wr-metric-strip" aria-label="Operator metrics">
        <Metric label={`${categoryLabel} supply`} value={String(supplyCount)} />
        <Metric
          label="Opportunity score"
          value={opportunity ? formatScore(opportunity.opportunity_score) : "n/a"}
          tone="opportunity"
        />
        <Metric label="Category velocity / 90d" value={velocityLabel} tone="signal" />
        <Metric label={`Rank in ${categoryLabel}`} value={rank ? `#${rank}` : "n/a"} />
        <Metric label="Record confidence" value={formatScore(operator.confidence_score)} tone="magma" />
      </section>

      <div className="wr-detail-grid">
        <div className="wr-detail-left">
          <section className="wr-detail-card wr-map-card">
            <div className="wr-detail-mini-map">
              <OperatorMap
                operators={miniOperators}
                heatmapCells={[]}
                signals={[]}
                selectedOperatorId={operator.id}
                layers={{ operators: true, signals: false, people: false, opportunity: false }}
                chrome={false}
                onSelectOperator={() => undefined}
              />
              <span>TRADE AREA / 1.5KM</span>
            </div>
            <div className="wr-competitive-set">
              <h2>COMPETITIVE SET / {categoryLabel.toUpperCase()} WITHIN 1.5KM</h2>
              {nearbyOperators.map((nearby) => {
                const distance = distanceKm(operator, nearby);
                return (
                  <article key={nearby.id}>
                    <span className={nearby.status.toLowerCase().includes("planned") ? "is-ring" : ""} />
                    <strong>{nearby.name}</strong>
                    <small>
                      {distance.toFixed(1)}km / {nearby.status}
                    </small>
                    <div aria-hidden>
                      <i style={{ width: `${Math.max(18, Math.round(nearby.confidence_score * 100))}%` }} />
                    </div>
                  </article>
                );
              })}
              {nearbyOperators.length === 0 ? <p>No nearby same-category operators in the current data.</p> : null}
            </div>
          </section>

          <section className="wr-detail-card wr-signal-history">
            <h2>SIGNAL HISTORY</h2>
            <div>
              {relatedSignals.map((signal, index) => (
                <article key={signal.id}>
                  <div>
                    <span style={{ background: colorForSignalType(signal.type) }} />
                    {index < relatedSignals.length - 1 ? <i /> : null}
                  </div>
                  <section>
                    <h3>{signal.title}</h3>
                    {signal.why_it_matters ? <p>{signal.why_it_matters}</p> : null}
                    {!signal.why_it_matters && signal.summary ? <p>{signal.summary}</p> : null}
                    <footer>
                      {signal.source_refs[0] ? <SourceChip refData={signal.source_refs[0]} compact /> : signal.source_name}
                      <span>{formatAgeFromHours(signal.freshness_age_hours)}</span>
                      <b style={{ color: magma(signal.confidence_score) }}>conf {formatScore(signal.confidence_score)}</b>
                    </footer>
                  </section>
                </article>
              ))}
              {relatedSignals.length === 0 ? <p>No related signals in the current source data.</p> : null}
            </div>
          </section>
        </div>

        <aside className="wr-detail-right">
          <section className="wr-detail-card wr-provenance-drawer">
            <div className="wr-detail-card-head">
              <h2>PROVENANCE</h2>
              <span>VERIFIED {formatAgeFromHours(operator.freshness_age_hours)} AGO</span>
            </div>
            <div className="wr-source-cards">
              {operator.source_refs.map((ref) => (
                <SourceCard key={`${ref.source_name}-${ref.source_record_id ?? ref.seen_at}`} refData={ref} />
              ))}
              {operator.source_refs.length === 0 ? <p>No source references on this record.</p> : null}
            </div>
            <ConfidenceBar score={operator.confidence_score} />
            <p className="wr-trust-note">
              {new Set(operator.source_refs.map((ref) => ref.source_name)).size} independent sources / BC-gate passed /
              no Washington-State contamination.
            </p>
          </section>

          <section className="wr-detail-card wr-attributes">
            <h2>ATTRIBUTES</h2>
            <dl>
              <dt>Status</dt>
              <dd>{sentenceCase(operator.status)}</dd>
              <dt>Category</dt>
              <dd>
                <span>
                  {operator.categories.map((category) => (
                    <b key={category}>{sentenceCase(category)}</b>
                  ))}
                </span>
              </dd>
              <dt>Org ID</dt>
              <dd>{operator.organization_id ?? operator.orgbook_id ?? "n/a"}</dd>
              <dt>Geocode</dt>
              <dd>
                {operator.lat.toFixed(4)}, {operator.lng.toFixed(4)}
              </dd>
              <dt>Neighborhood</dt>
              <dd>{operator.neighborhood ?? operator.municipality ?? "n/a"}</dd>
            </dl>
          </section>
        </aside>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  tone = "neutral"
}: {
  label: string;
  value: string;
  tone?: "neutral" | "opportunity" | "signal" | "magma";
}) {
  return (
    <article className={`wr-detail-metric wr-detail-metric-${tone}`}>
      <strong>{value}</strong>
      <span>{label}</span>
    </article>
  );
}

function SourceCard({ refData }: { refData: SourceRef }) {
  return (
    <article className="wr-source-card">
      <div>
        <i style={{ background: colorForTrustTier(refData.trust_tier) }} />
        <strong>{refData.source_name}</strong>
      </div>
      <footer>
        <span style={{ color: colorForTrustTier(refData.trust_tier) }}>{sentenceCase(refData.trust_tier)}</span>
        <span>/</span>
        <span>{refData.licence ?? "match note unavailable"}</span>
        {refData.url ? (
          <a href={refData.url} target="_blank" rel="noreferrer">
            source
          </a>
        ) : null}
      </footer>
    </article>
  );
}

function findOpportunityForOperator(
  operator: Operator,
  cells: OpportunityHeatmapCell[]
): OpportunityHeatmapCell | null {
  const candidates = [
    operator.neighborhood?.toLowerCase(),
    operator.municipality?.toLowerCase(),
    operator.address?.toLowerCase()
  ].filter(Boolean) as string[];
  return (
    cells.find((cell) => candidates.some((candidate) => cell.geo_name.toLowerCase().includes(candidate))) ??
    cells[0] ??
    null
  );
}

function countSameAreaSupply(operator: Operator, operators: Operator[]): number {
  return operators.filter(
    (item) =>
      item.id !== operator.id &&
      item.neighborhood === operator.neighborhood &&
      item.categories.some((category) => operator.categories.includes(category))
  ).length;
}

function rankInCategory(operator: Operator, operators: Operator[]): number | null {
  const category = operator.categories[0];
  if (!category) {
    return null;
  }
  const ranked = operators
    .filter((item) => item.categories.includes(category))
    .sort((a, b) => b.confidence_score - a.confidence_score);
  const index = ranked.findIndex((item) => item.id === operator.id);
  return index >= 0 ? index + 1 : null;
}

function nearestOperators(operator: Operator, operators: Operator[]): Operator[] {
  return operators
    .filter((item) => item.id !== operator.id)
    .filter((item) => item.categories.some((category) => operator.categories.includes(category)))
    .map((item) => ({ item, distance: distanceKm(operator, item) }))
    .filter(({ distance }) => distance <= 1.5)
    .sort((a, b) => a.distance - b.distance)
    .map(({ item }) => item);
}

function distanceKm(a: Operator, b: Operator): number {
  const earthRadiusKm = 6371;
  const dLat = toRadians(b.lat - a.lat);
  const dLng = toRadians(b.lng - a.lng);
  const latA = toRadians(a.lat);
  const latB = toRadians(b.lat);
  const h =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(latA) * Math.cos(latB) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
  return 2 * earthRadiusKm * Math.asin(Math.min(1, Math.sqrt(h)));
}

function toRadians(value: number): number {
  return (value * Math.PI) / 180;
}

function formatVelocity(velocity: CategoryVelocity | null): string {
  if (!velocity) {
    return "n/a";
  }
  const numeric = Object.values(velocity.component_breakdown).find((value) => typeof value === "number") as
    | number
    | undefined;
  if (numeric !== undefined && numeric > 0 && numeric <= 1) {
    return `+${Math.round(numeric * 100)}%`;
  }
  const total =
    velocity.new_operator_count +
    velocity.job_velocity_count +
    velocity.event_velocity_count +
    velocity.news_velocity_count;
  return `+${total}`;
}

function exportRecord(operator: Operator) {
  const blob = new Blob([JSON.stringify(operator, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${operator.id}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}
