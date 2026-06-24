import { useState } from "react";
import { MapPin } from "lucide-react";
import type { CoverageMeta } from "../../lib/api";

interface CoverageBadgeProps {
  coverage: CoverageMeta | null;
}

function formatCount(value: number): string {
  return value.toLocaleString("en-CA");
}

export function CoverageBadge({ coverage }: CoverageBadgeProps) {
  const [open, setOpen] = useState(false);

  if (!coverage || coverage.operator_count === 0) {
    return null;
  }

  const { operator_count, municipality_count, municipalities } = coverage;
  const top = municipalities.slice(0, 12);

  return (
    <div className="wr-coverage" onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        className="wr-coverage-chip"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        onMouseEnter={() => setOpen(true)}
      >
        <MapPin size={13} aria-hidden />
        <strong>{formatCount(operator_count)}</strong>
        <span>places</span>
        <i aria-hidden>·</i>
        <strong>{municipality_count}</strong>
        <span>municipalities</span>
      </button>
      {open ? (
        <div className="wr-coverage-pop" role="dialog" aria-label="Coverage by municipality">
          <header>
            <span>Live coverage</span>
            <small>source-backed operators &amp; civic facilities</small>
          </header>
          <ul>
            {top.map((item) => (
              <li key={item.name}>
                <span>{item.name}</span>
                <strong>{formatCount(item.operator_count)}</strong>
              </li>
            ))}
          </ul>
          {municipalities.length > top.length ? (
            <footer>+{municipalities.length - top.length} more municipalities</footer>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
