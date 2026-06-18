import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { SourceFreshness } from "../../lib/api";

type Props = {
  sources: SourceFreshness[];
};

export function SourceFreshnessPanel({ sources }: Props) {
  const stale = sources.filter((source) => source.is_stale).length;
  return (
    <section className="sideSection" aria-label="Source freshness">
      <div className="sectionHeader">
        <h2>Sources</h2>
        <span>{stale} stale</span>
      </div>
      <div className="sourceFreshnessList">
        {sources.map((source) => (
          <div key={source.source_name} className="freshnessRow">
            <span className={source.is_stale ? "statusDot stale" : "statusDot fresh"}>
              {source.is_stale ? <AlertTriangle size={13} /> : <CheckCircle2 size={13} />}
            </span>
            <div>
              <strong>{source.source_name}</strong>
              <small>
                {source.latest_status ?? "not run"} · rejected {source.rejected_count}
              </small>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
