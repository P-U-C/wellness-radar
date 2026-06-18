import { TrendingUp } from "lucide-react";
import type { TrendTile } from "../../lib/api";

type Props = {
  trends: TrendTile[];
};

export function TrendTiles({ trends }: Props) {
  const terms = Array.from(new Set(trends.map((trend) => trend.term))).slice(0, 4);
  return (
    <section className="sideSection" aria-label="Peer-city trends">
      <div className="sectionHeader">
        <h2>Trends</h2>
        <span>{trends.some((trend) => trend.is_stub) ? "stub" : "live"}</span>
      </div>
      <div className="trendTiles">
        {terms.map((term) => {
          const rows = trends.filter((trend) => trend.term === term);
          const vancouver = rows.find((trend) => trend.city === "Vancouver");
          return (
            <article className="trendTile" key={term}>
              <div className="trendTitle">
                <strong>{term}</strong>
                <span>{vancouver?.growth_class ?? "n/a"}</span>
              </div>
              {vancouver ? <Sparkline values={vancouver.series.map((point) => point.value)} /> : null}
              <div className="peerRow">
                {rows.slice(0, 5).map((trend) => (
                  <span key={`${trend.term}-${trend.city}`}>
                    {trend.city.slice(0, 3)}
                    <b>{trend.series.at(-1)?.value ?? 0}</b>
                  </span>
                ))}
              </div>
            </article>
          );
        })}
      </div>
      {trends.length === 0 ? (
        <p className="emptyInline">
          <TrendingUp size={14} /> Run the M3 trend provider.
        </p>
      ) : null}
    </section>
  );
}

function Sparkline({ values }: { values: number[] }) {
  const width = 154;
  const height = 42;
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = Math.max(max - min, 1);
  const points = values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * width;
      const y = height - ((value - min) / range) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg className="sparkline" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Trend sparkline">
      <polyline points={points} fill="none" stroke="#2bd4a7" strokeWidth="3" />
    </svg>
  );
}
