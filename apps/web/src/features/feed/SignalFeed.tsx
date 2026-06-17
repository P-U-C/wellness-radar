import { AlertCircle, ExternalLink, MapPin } from "lucide-react";
import type { Signal } from "../../lib/api";

type Props = {
  loading: boolean;
  error: string | null;
  signals: Signal[];
  selectedOperatorId: string | null;
  onSelectOperator: (operatorId: string) => void;
};

export function SignalFeed({ loading, error, signals, selectedOperatorId, onSelectOperator }: Props) {
  return (
    <aside className="feedRail" aria-label="Signal feed">
      <div className="railHeader">
        <h2>Signals</h2>
        <span>{signals.length}</span>
      </div>
      {loading ? <p className="emptyState">Loading source-backed signals...</p> : null}
      {error ? (
        <p className="errorState">
          <AlertCircle size={16} /> {error}
        </p>
      ) : null}
      {!loading && !error && signals.length === 0 ? (
        <p className="emptyState">Waiting for the City licence adapter to ingest records.</p>
      ) : null}
      <div className="feedList">
        {signals.map((signal) => (
          <article
            key={signal.id}
            className={
              signal.related_operator_id === selectedOperatorId ? "signalCard selected" : "signalCard"
            }
          >
            <button
              type="button"
              className="cardButton"
              onClick={() => signal.related_operator_id && onSelectOperator(signal.related_operator_id)}
            >
              <span className={`severity ${signal.severity}`}>{signal.severity}</span>
              <h3>{signal.title}</h3>
              <p>{signal.summary}</p>
              <small>{signal.why_it_matters}</small>
              <span className="signalMeta">
                <MapPin size={14} />
                {new Date(signal.occurred_at).toLocaleDateString()}
                <strong>{Math.round(signal.confidence_score * 100)}%</strong>
              </span>
            </button>
            <div className="sourceLine">
              <span>{signal.source_name}</span>
              <span>{signal.trust_tier}</span>
              {signal.source_url ? (
                <a href={signal.source_url} target="_blank" rel="noreferrer" title="Open source">
                  <ExternalLink size={14} />
                </a>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </aside>
  );
}
