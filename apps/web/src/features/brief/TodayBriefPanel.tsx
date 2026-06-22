import { CalendarDays, CheckCircle2, ExternalLink, Radar } from "lucide-react";
import { SourceChip } from "../../components";
import type { BriefSectionItem, DailyBrief } from "../../lib/api";
import { formatAgeFromIso, formatScore, sentenceCase } from "../../lib/format";

type Props = {
  brief: DailyBrief | null;
  loading: boolean;
  error: string | null;
};

const SECTION_LABELS: Array<{ key: keyof DailyBrief["sections"]; label: string }> = [
  { key: "changed_operators", label: "Changed Operators" },
  { key: "new_signals", label: "New Signals" },
  { key: "opportunity_movement", label: "Opportunity Movement" },
  { key: "new_reachable_leads", label: "New Leads" }
];

export function TodayBriefPanel({ brief, loading, error }: Props) {
  return (
    <aside className="wr-brief-panel" aria-label="Today market brief">
      <header className="wr-brief-head">
        <div>
          <span>Today</span>
          <h1>Market Brief</h1>
        </div>
        <BriefStatus brief={brief} loading={loading} error={error} />
      </header>

      {loading ? <p className="wr-brief-state">Loading daily brief...</p> : null}
      {!loading && error ? <p className="wr-brief-state is-error">{error}</p> : null}
      {!loading && !error && !brief ? (
        <p className="wr-brief-state">No daily brief has been generated yet.</p>
      ) : null}

      {brief ? (
        <>
          <div className="wr-brief-meta">
            <span>
              <CalendarDays size={13} />
              {brief.brief_date}
            </span>
            <span>{formatAgeFromIso(brief.generated_at)}</span>
          </div>

          <section className="wr-brief-actions" aria-label="Recommended actions">
            <h2>TOP ACTIONS</h2>
            {brief.top_actions.slice(0, 3).map((action, index) => (
              <article key={action.id}>
                <b>{index + 1}</b>
                <div>
                  <strong>{action.title}</strong>
                  <p>{action.summary}</p>
                  <div className="wr-brief-sources">
                    {action.source_refs.slice(0, 2).map((ref) => (
                      <SourceChip key={`${action.id}-${ref.source_name}-${ref.source_record_id ?? ref.seen_at}`} refData={ref} compact />
                    ))}
                  </div>
                </div>
              </article>
            ))}
            {brief.top_actions.length === 0 ? (
              <p className="wr-brief-empty">No material action today.</p>
            ) : null}
          </section>

          <div className="wr-brief-sections">
            {SECTION_LABELS.map(({ key, label }) => (
              <BriefSection key={key} label={label} items={brief.sections[key] ?? []} />
            ))}
          </div>
        </>
      ) : null}
    </aside>
  );
}

function BriefStatus({
  brief,
  loading,
  error
}: {
  brief: DailyBrief | null;
  loading: boolean;
  error: string | null;
}) {
  if (loading) {
    return (
      <span className="wr-brief-status">
        <Radar size={13} />
        sync
      </span>
    );
  }
  if (error) {
    return (
      <span className="wr-brief-status is-error">
        <ExternalLink size={13} />
        error
      </span>
    );
  }
  if (!brief) {
    return (
      <span className="wr-brief-status">
        <Radar size={13} />
        waiting
      </span>
    );
  }
  return (
    <span className={`wr-brief-status is-${brief.status}`}>
      <CheckCircle2 size={13} />
      {brief.status === "material_changes" ? "changes" : sentenceCase(brief.status)}
    </span>
  );
}

function BriefSection({ label, items }: { label: string; items: BriefSectionItem[] }) {
  return (
    <section className="wr-brief-section">
      <h2>
        {label}
        <b>{items.length}</b>
      </h2>
      {items.slice(0, 4).map((item) => (
        <article key={item.id}>
          <div>
            <strong>{item.title}</strong>
            <span>{briefItemMetric(item)}</span>
          </div>
          <p>{item.summary}</p>
          <div className="wr-brief-sources">
            {item.source_refs.slice(0, 2).map((ref) => (
              <SourceChip key={`${item.id}-${ref.source_name}-${ref.source_record_id ?? ref.seen_at}`} refData={ref} compact />
            ))}
          </div>
        </article>
      ))}
      {items.length === 0 ? <p className="wr-brief-empty">No source-backed changes.</p> : null}
    </section>
  );
}

function briefItemMetric(item: BriefSectionItem): string {
  if (typeof item.opportunity_score === "number") {
    const delta = typeof item.delta === "number" ? ` / ${item.delta >= 0 ? "+" : ""}${item.delta.toFixed(2)}` : "";
    return `${formatScore(item.opportunity_score)}${delta}`;
  }
  if (item.severity) {
    return sentenceCase(item.severity);
  }
  if (item.contact_count) {
    return `${item.contact_count} contact${item.contact_count === 1 ? "" : "s"}`;
  }
  if (item.status) {
    return sentenceCase(item.status);
  }
  return sentenceCase(item.item_type);
}
