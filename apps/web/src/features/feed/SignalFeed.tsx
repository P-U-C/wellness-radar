import { AlertCircle } from "lucide-react";
import { SignalCard } from "../../components";
import type { Signal } from "../../lib/api";

type Props = {
  loading: boolean;
  error: string | null;
  signals: Signal[];
  selectedOperatorId: string | null;
  selectedSignalId: string | null;
  onSelectSignal: (signal: Signal) => void;
  onClearSelection: () => void;
  onViewAll: () => void;
};

export function SignalFeed({
  loading,
  error,
  signals,
  selectedOperatorId,
  selectedSignalId,
  onSelectSignal,
  onClearSelection,
  onViewAll
}: Props) {
  const visibleSignals = signals.slice(0, 6);
  const earlierCount = Math.max(0, signals.length - visibleSignals.length);

  return (
    <aside className="wr-feed-strip" aria-label="Signal feed">
      <div className="wr-feed-head">
        <span>SIGNAL FEED · LAST 24H</span>
        <button type="button" onClick={onViewAll}>
          view all ↗
        </button>
        {selectedOperatorId ? (
          <button type="button" onClick={onClearSelection}>
            clear focus
          </button>
        ) : null}
        <i />
        <b>now</b>
      </div>
      {loading ? <p className="wr-feed-state">Loading source-backed signals...</p> : null}
      {error ? (
        <p className="wr-feed-state is-error">
          <AlertCircle size={15} /> {error}
        </p>
      ) : null}
      {!loading && !error && signals.length === 0 ? (
        <p className="wr-feed-state">No source-backed signals match the current filters.</p>
      ) : null}
      {!loading && !error && signals.length > 0 ? (
        <div className="wr-feed-row">
          {visibleSignals.map((signal) => (
            <SignalCard
              key={signal.id}
              signal={signal}
              selected={signal.id === selectedSignalId}
              variant="strip"
              onSelect={onSelectSignal}
            />
          ))}
          <div className="wr-feed-more">
            +{earlierCount}
            <br />
            earlier
          </div>
        </div>
      ) : null}
    </aside>
  );
}
