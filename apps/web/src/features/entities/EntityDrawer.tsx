import { ExternalLink, X } from "lucide-react";
import type { Operator, Signal } from "../../lib/api";

type Props = {
  operator: Operator | null;
  signals: Signal[];
  nearbyOperators: Operator[];
  onClose: () => void;
};

export function EntityDrawer({ operator, signals, nearbyOperators, onClose }: Props) {
  if (!operator) {
    return null;
  }

  return (
    <aside className="drawer" aria-label="Entity drawer">
      <button className="drawerClose" type="button" onClick={onClose} title="Close">
        <X size={18} />
      </button>
      <section className="drawerSection">
        <span className="eyebrow">{operator.status}</span>
        <h2>{operator.name}</h2>
        <p>{operator.address}</p>
        <small className="drawerMeta">
          {operator.source_refs.length} refs · {formatFreshness(operator.freshness_age_hours)}
        </small>
        <div className="categoryRow">
          {operator.categories.map((category) => (
            <span key={category}>{category.replaceAll("_", " ")}</span>
          ))}
        </div>
      </section>

      <section className="drawerSection">
        <h3>Licence</h3>
        <dl className="definitionGrid">
          <dt>Municipality</dt>
          <dd>{operator.municipality}</dd>
          <dt>Area</dt>
          <dd>{operator.neighborhood ?? "Unspecified"}</dd>
          <dt>Confidence</dt>
          <dd>{Math.round(operator.confidence_score * 100)}%</dd>
        </dl>
      </section>

      <section className="drawerSection">
        <h3>Timeline</h3>
        <div className="timeline">
          {signals.map((signal) => (
            <div key={signal.id}>
              <time>{new Date(signal.occurred_at).toLocaleDateString()}</time>
              <span>{signal.title}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="drawerSection">
        <h3>Nearby</h3>
        <div className="nearbyList">
          {nearbyOperators.slice(0, 6).map((nearby) => (
            <span key={nearby.id}>{nearby.name}</span>
          ))}
          {nearbyOperators.length === 0 ? <span>No same-area operators in the current view.</span> : null}
        </div>
      </section>

      <section className="drawerSection">
        <h3>Provenance</h3>
        <div className="provenanceList">
          {operator.source_refs.map((ref) => (
            <div key={`${ref.source_name}-${ref.source_record_id}`}>
              <strong>{ref.source_name}</strong>
              <span>{ref.trust_tier}</span>
              <time>{new Date(ref.seen_at).toLocaleString()}</time>
              {ref.url ? (
                <a href={ref.url} target="_blank" rel="noreferrer">
                  <ExternalLink size={14} /> Source
                </a>
              ) : null}
            </div>
          ))}
        </div>
      </section>
    </aside>
  );
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
