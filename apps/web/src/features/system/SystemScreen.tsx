import { useMemo } from "react";
import { AlertTriangle, Database, Gauge, RefreshCw } from "lucide-react";
import type {
  CoverageMeta,
  ObservabilitySummary,
  SourceFreshness,
  SourceRun,
} from "../../lib/api";
import { formatAgeFromHours, formatAgeFromIso, sentenceCase } from "../../lib/format";

interface SystemScreenProps {
  sources: SourceFreshness[];
  runs: SourceRun[];
  observability: ObservabilitySummary | null;
  coverage: CoverageMeta | null;
  counts: { signals: number; people: number; bundles: number };
}

function freshnessState(source: SourceFreshness): "ok" | "stale" | "down" {
  if (source.latest_status && source.latest_status !== "success") {
    return "down";
  }
  if (source.is_stale || source.latest_status === null) {
    return "stale";
  }
  return "ok";
}

function formatCount(value: number): string {
  return value.toLocaleString("en-CA");
}

export function SystemScreen({
  sources,
  runs,
  observability,
  coverage,
  counts,
}: SystemScreenProps) {
  const sorted = useMemo(() => {
    const order = { down: 0, stale: 1, ok: 2 };
    return [...sources].sort((a, b) => {
      const sa = order[freshnessState(a)];
      const sb = order[freshnessState(b)];
      if (sa !== sb) return sa - sb;
      return a.source_name.localeCompare(b.source_name);
    });
  }, [sources]);

  const liveSources = sources.filter((s) => s.enabled).length;
  const staleSources = sources.filter((s) => freshnessState(s) !== "ok").length;
  const lastUpdate = useMemo(() => {
    const ages = sources
      .map((s) => s.age_hours)
      .filter((value): value is number => typeof value === "number");
    return ages.length ? Math.min(...ages) : null;
  }, [sources]);

  const contact = observability?.database?.wellness_contact_coverage;
  const runtime = observability?.runtime;
  const firing = (observability?.alerts ?? []).filter((a) => a.firing);
  const errorRate =
    runtime && runtime.api_requests_total > 0
      ? runtime.api_errors_total / runtime.api_requests_total
      : 0;

  return (
    <section className="wr-system-screen" aria-label="System status">
      <div className="wr-system-inner">
        <header className="wr-system-head">
          <span>SYSTEM STATUS</span>
          <h1>Data sources &amp; pipeline health</h1>
          <p>
            What the radar is running on right now — live sources, freshness, ingestion
            history, and deal-flow readiness.
          </p>
        </header>

        {firing.length > 0 ? (
          <div className="wr-sys-alerts" role="status">
            {firing.map((a) => (
              <div key={a.condition} className={`wr-sys-alert is-${a.severity}`}>
                <AlertTriangle size={14} />
                <strong>{sentenceCase(a.condition)}</strong>
                <span>{a.summary}</span>
              </div>
            ))}
          </div>
        ) : null}

        <div className="wr-sys-stat-grid">
          <StatCard label="Mapped places" value={coverage ? formatCount(coverage.operator_count) : "—"} sub={coverage ? `${coverage.municipality_count} municipalities` : ""} />
          <StatCard label="Live sources" value={`${liveSources}`} sub={staleSources ? `${staleSources} stale / erroring` : "all fresh"} tone={staleSources ? "warn" : "ok"} />
          <StatCard label="Last ingest" value={lastUpdate === null ? "—" : formatAgeFromHours(lastUpdate)} sub="most-recent source" />
          <StatCard label="Signals" value={formatCount(counts.signals)} sub={`${formatCount(counts.people)} people · ${counts.bundles} bundles`} />
        </div>

        <section className="wr-system-section">
          <h2><Database size={15} /> Data sources <b>{sources.length}</b></h2>
          <div className="wr-source-table" role="table">
            <div className="wr-source-row is-head" role="row">
              <span>Source</span>
              <span>Trust</span>
              <span>Cadence</span>
              <span>Last update</span>
              <span>Records</span>
              <span>Status</span>
            </div>
            {sorted.map((s) => {
              const state = freshnessState(s);
              return (
                <div key={s.source_name} className="wr-source-row" role="row">
                  <span className="wr-source-name">
                    <i className={`wr-dot is-${state}`} />
                    <b>{sentenceCase(s.source_name)}</b>
                    <small>{sentenceCase(s.family)}</small>
                  </span>
                  <span className={`wr-tier is-${s.trust_tier}`}>{sentenceCase(s.trust_tier)}</span>
                  <span className="wr-mono">{s.cadence}</span>
                  <span className="wr-mono">{formatAgeFromHours(s.age_hours)}{s.age_hours !== null ? " ago" : ""}</span>
                  <span className="wr-mono">{s.records_persisted ?? "—"}</span>
                  <span className={`wr-source-status is-${state}`}>
                    {state === "ok" ? "fresh" : state === "stale" ? "stale" : "error"}
                  </span>
                </div>
              );
            })}
          </div>
          <p className="wr-source-foot">
            Cadence = how often each source re-ingests. “Stale” means it has passed its freshness
            SLA — the scheduler will refresh it on its next cycle. Trust tier drives how heavily a
            record is weighted across the console.
          </p>
        </section>

        {contact ? (
          <section className="wr-system-section">
            <h2><Gauge size={15} /> Deal-flow readiness</h2>
            <div className="wr-sys-stat-grid is-compact">
              <StatCard label="Operators w/ contact" value={formatCount(contact.with_contact_count)} sub={`${Math.round(contact.coverage_ratio * 100)}% of ${formatCount(contact.operator_count)}`} />
              <StatCard label="With phone" value={formatCount(contact.with_phone_count)} />
              <StatCard label="With email" value={formatCount(contact.with_email_count)} />
              <StatCard label="With website" value={formatCount(contact.with_website_count)} />
            </div>
          </section>
        ) : null}

        <section className="wr-system-section">
          <h2><RefreshCw size={15} /> Recent ingestion runs</h2>
          <div className="wr-run-list">
            {runs.length === 0 ? <p className="wr-source-foot">No runs recorded yet.</p> : null}
            {runs.map((run) => (
              <div key={run.id} className="wr-run-row">
                <span className="wr-source-name">
                  <i className={`wr-dot is-${run.status === "success" ? "ok" : "down"}`} />
                  <b>{sentenceCase(run.source_name)}</b>
                </span>
                <span className="wr-mono">{run.completed_at ? `${formatAgeFromIso(run.completed_at)} ago` : "running"}</span>
                <span className="wr-mono wr-run-counts">
                  +{run.records_persisted} kept
                  {run.records_rejected ? ` · ${run.records_rejected} rejected` : ""}
                  {run.error_count ? ` · ${run.error_count} err` : ""}
                </span>
              </div>
            ))}
          </div>
        </section>

        {runtime ? (
          <section className="wr-system-section">
            <h2><Gauge size={15} /> API runtime</h2>
            <div className="wr-sys-stat-grid is-compact">
              <StatCard label="Requests" value={formatCount(runtime.api_requests_total)} />
              <StatCard label="Error rate" value={`${(errorRate * 100).toFixed(1)}%`} tone={errorRate > 0.02 ? "warn" : "ok"} />
              <StatCard label="API latency" value={`${Math.round(runtime.api_latency_ms_avg)}ms`} sub="avg" />
              <StatCard label="Map query" value={`${Math.round(runtime.map_query_latency_ms_avg)}ms`} sub="avg" />
            </div>
          </section>
        ) : null}
      </div>
    </section>
  );
}

function StatCard({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "ok" | "warn";
}) {
  return (
    <div className={`wr-stat-card${tone ? ` is-${tone}` : ""}`}>
      <span className="wr-stat-label">{label}</span>
      <strong className="wr-stat-value">{value}</strong>
      {sub ? <span className="wr-stat-sub">{sub}</span> : null}
    </div>
  );
}
