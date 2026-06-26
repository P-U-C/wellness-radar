import { TrendingUp } from "lucide-react";
import type { TrendTile } from "../../lib/api";

type Props = {
  trends: TrendTile[];
};

export function TrendTiles({ trends }: Props) {
  const terms = Array.from(new Set(trends.map((trend) => trend.term))).slice(0, 4);
  const pending = trends.length === 0 || trends.some((trend) => trend.is_stub || trend.source_status === "data_pending");
  return (
    <section className="sideSection" aria-label="Peer-city trends">
      <div className="sectionHeader">
        <h2>Trends</h2>
        <span className={pending ? "is-pending" : ""}>{pending ? "data pending" : "live"}</span>
      </div>
      <div className="trendTiles">
        {terms.map((term) => {
          const rows = trends.filter((trend) => trend.term === term);
          const vancouver = rows.find((trend) => trend.city === "Vancouver");
          const rowPending = rows.some((trend) => trend.is_stub || trend.source_status === "data_pending");
          return (
            <article className="trendTile" key={term}>
              <div className="trendTitle">
                <strong>{term}</strong>
                <span className={rowPending ? "is-pending" : ""}>
                  {rowPending ? "data pending" : (vancouver?.growth_class ?? "n/a")}
                </span>
              </div>
              {vancouver && !rowPending ? <Sparkline values={vancouver.series.map((point) => point.value)} /> : null}
              {!rowPending ? (
                <div className="peerRow">
                  {rows.slice(0, 5).map((trend) => (
                    <span key={`${trend.term}-${trend.city}`}>
                      {trend.city.slice(0, 3)}
                      <b>{trend.series.at(-1)?.value ?? 0}</b>
                    </span>
                  ))}
                </div>
              ) : (
                <p className="trendPending">Live demand series not available.</p>
              )}
            </article>
          );
        })}
      </div>
      {trends.length === 0 ? (
        <p className="emptyInline">
          <TrendingUp size={14} /> Live trend demand is pending; fixture breakout tiles are hidden.
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
