import type { SourceRef } from "../lib/api";
import { formatVerified } from "../lib/format";
import { ConfidenceBar } from "./ConfidenceBar";
import { SourceChip } from "./SourceChip";

type Props = {
  source_refs: SourceRef[];
  confidence_score: number;
  freshness_age_hours?: number | null;
  compact?: boolean;
};

export function ProvenanceBlock({
  source_refs,
  confidence_score,
  freshness_age_hours,
  compact = false
}: Props) {
  const independentCount = new Set(source_refs.map((ref) => ref.source_name)).size;
  const hasOfficial = source_refs.some((ref) => ref.trust_tier === "official");
  const note = [
    `${independentCount} independent ${independentCount === 1 ? "source" : "sources"}`,
    hasOfficial ? "official source present" : "non-official corroboration",
    "BC-gated"
  ].join(" / ");

  return (
    <section className="wr-provenance" aria-label="Provenance">
      <div className="wr-provenance-head">
        <span>PROVENANCE</span>
        <strong>{formatVerified(freshness_age_hours)}</strong>
      </div>
      <div className="wr-source-stack">
        {source_refs.slice(0, compact ? 2 : 5).map((ref) => (
          <SourceChip key={`${ref.source_name}-${ref.source_record_id ?? ref.seen_at}`} refData={ref} />
        ))}
        {source_refs.length === 0 ? <span className="wr-muted">No source references</span> : null}
      </div>
      <ConfidenceBar score={confidence_score} />
      {!compact ? <p className="wr-trust-note">{note}</p> : null}
    </section>
  );
}
