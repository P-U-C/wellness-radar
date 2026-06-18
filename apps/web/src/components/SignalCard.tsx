import { MapPin } from "lucide-react";
import type { CSSProperties } from "react";
import type { Signal } from "../lib/api";
import { formatAgeFromHours, formatScore, sentenceCase } from "../lib/format";
import { colorForSignalType, magma } from "../lib/theme";
import { SourceChip } from "./SourceChip";

type Props = {
  signal: Signal;
  selected?: boolean;
  variant?: "strip" | "stream" | "timeline";
  context?: string | null;
  actionLabel?: string;
  onSelect?: (signal: Signal) => void;
};

export function SignalCard({
  signal,
  selected = false,
  variant = "stream",
  context,
  actionLabel,
  onSelect
}: Props) {
  const accent = colorForSignalType(signal.type || signal.severity);
  const source = signal.source_refs[0];
  const isButton = Boolean(onSelect);

  const body = (
    <>
      <div className="wr-signal-meta">
        <span className="wr-signal-type" style={{ color: accent }}>
          {sentenceCase(signal.type || signal.severity)}
        </span>
        {context ? <span className="wr-signal-context">{context}</span> : null}
        <span>{signal.freshness_age_hours !== undefined ? formatAgeFromHours(signal.freshness_age_hours) : formatSignalAge(signal.occurred_at)}</span>
      </div>
      <h3>{signal.title}</h3>
      {variant !== "strip" && signal.why_it_matters ? <p>{signal.why_it_matters}</p> : null}
      {variant !== "strip" && !signal.why_it_matters && signal.summary ? <p>{signal.summary}</p> : null}
      <div className="wr-signal-foot">
        {source ? (
          <SourceChip refData={source} compact={variant === "strip"} disableLink={isButton} />
        ) : (
          <span>{signal.source_name}</span>
        )}
        <span className="wr-signal-confidence" style={{ color: magma(signal.confidence_score) }}>
          conf {formatScore(signal.confidence_score)}
        </span>
        {signal.lat !== null && signal.lng !== null ? (
          actionLabel ? (
            <span className="wr-signal-action">
              <MapPin aria-hidden size={13} /> {actionLabel}
            </span>
          ) : (
            <MapPin aria-hidden size={13} />
          )
        ) : null}
      </div>
    </>
  );

  return (
    <article
      className={`wr-signal-card wr-signal-${variant}${selected ? " is-selected" : ""}`}
      style={{ "--wr-signal-accent": accent } as CSSProperties}
    >
      {isButton ? (
        <button type="button" onClick={() => onSelect?.(signal)}>
          {body}
        </button>
      ) : (
        body
      )}
    </article>
  );
}

function formatSignalAge(occurredAt: string): string {
  const hours = Math.max(0, (Date.now() - Date.parse(occurredAt)) / 3_600_000);
  return formatAgeFromHours(hours);
}
