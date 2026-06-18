import { formatScore } from "../lib/format";
import { magma } from "../lib/theme";
import type { CSSProperties } from "react";

type Props = {
  score: number;
  label?: string;
};

export function ConfidenceBar({ score, label = "CONF" }: Props) {
  const normalized = Math.max(0, Math.min(1, score));
  const color = magma(normalized);

  return (
    <div className="wr-confidence" style={{ "--wr-score-color": color } as CSSProperties}>
      <span>{label}</span>
      <div className="wr-confidence-track" aria-hidden>
        <div className="wr-confidence-fill" style={{ width: `${normalized * 100}%` }} />
      </div>
      <strong>{formatScore(normalized)}</strong>
    </div>
  );
}
