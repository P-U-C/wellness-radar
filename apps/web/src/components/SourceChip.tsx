import { ExternalLink } from "lucide-react";
import type { SourceRef } from "../lib/api";
import { formatAgeFromIso, sentenceCase } from "../lib/format";
import { colorForTrustTier } from "../lib/theme";

type Props = {
  refData: SourceRef;
  compact?: boolean;
  disableLink?: boolean;
};

export function SourceChip({ refData, compact = false, disableLink = false }: Props) {
  const tier = refData.trust_tier;
  const content = (
    <>
      <span className="wr-source-dot" style={{ background: colorForTrustTier(tier) }} />
      <span className="wr-source-name">{refData.source_name}</span>
      {!compact ? <span className="wr-source-tier">{sentenceCase(tier)}</span> : null}
      <span className="wr-source-age">{formatAgeFromIso(refData.seen_at)}</span>
      {refData.url ? <ExternalLink aria-hidden size={12} /> : null}
    </>
  );

  if (refData.url && !disableLink) {
    return (
      <a className="wr-source-chip" href={refData.url} target="_blank" rel="noreferrer">
        {content}
      </a>
    );
  }

  return <span className="wr-source-chip">{content}</span>;
}
