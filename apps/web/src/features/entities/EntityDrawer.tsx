import { AtSign, Globe2, Mail, Phone, X } from "lucide-react";
import { EntityBadge, ProvenanceBlock } from "../../components";
import type { ContactMethod, Operator, Signal } from "../../lib/api";
import { formatAgeFromHours, formatScore, sentenceCase } from "../../lib/format";
import { colorForSignalType } from "../../lib/theme";

type Props = {
  operator: Operator | null;
  signals: Signal[];
  nearbyOperators: Operator[];
  supplyCount: number | null;
  opportunityScore: number | null;
  velocityLabel: string;
  onClose: () => void;
  onOpenOperator: (operatorId: string) => void;
};

export function EntityDrawer({
  operator,
  signals,
  nearbyOperators,
  supplyCount,
  opportunityScore,
  velocityLabel,
  onClose,
  onOpenOperator
}: Props) {
  if (!operator) {
    return null;
  }

  return (
    <aside className="wr-inspector" aria-label="Selected operator inspector">
      <button className="wr-inspector-close" type="button" onClick={onClose} title="Close inspector">
        <X size={16} />
      </button>
      <div className="wr-inspector-head">
        <div>
          <div className="wr-inspector-badges">
            <EntityBadge type="operator" label="OPERATOR" />
            <EntityBadge type="signal" label={operator.status} />
          </div>
          <h2>{operator.name}</h2>
          <p>
            {operator.neighborhood ?? operator.municipality ?? "Metro Vancouver"} /{" "}
            {operator.categories.slice(0, 2).map(sentenceCase).join(" / ")}
          </p>
        </div>
        <button className="wr-open-record" type="button" onClick={() => onOpenOperator(operator.id)}>
          OPEN
        </button>
      </div>

      <div className="wr-inspector-metrics">
        <MetricTile label="SUPPLY" value={supplyCount !== null ? String(supplyCount) : "n/a"} />
        <MetricTile
          label="OPP SCORE"
          value={opportunityScore !== null ? formatScore(opportunityScore) : "n/a"}
          tone="opportunity"
        />
        <MetricTile label="VELOCITY" value={velocityLabel} tone="signal" />
        <MetricTile label="CONTACTS" value={String(operator.contacts?.length ?? 0)} tone="signal" />
      </div>

      <section className="wr-related-signals wr-contact-mini">
        <h3>PUBLIC CONTACTS</h3>
        <div>
          {(operator.contacts ?? []).slice(0, 3).map((contact) => (
            <ContactMini key={`${contact.type}-${contact.platform ?? ""}-${contact.value}`} contact={contact} />
          ))}
          {(operator.contacts ?? []).length === 0 ? <p>No source-backed contact method in current data.</p> : null}
        </div>
      </section>

      <ProvenanceBlock
        source_refs={operator.source_refs}
        confidence_score={operator.confidence_score}
        freshness_age_hours={operator.freshness_age_hours}
        compact
      />

      <section className="wr-related-signals">
        <h3>RELATED SIGNALS</h3>
        <div>
          {signals.slice(0, 4).map((signal) => (
            <article key={signal.id}>
              <span style={{ background: colorForSignalType(signal.type) }} />
              <div>
                <strong>{signal.title}</strong>
                <small>
                  {signal.source_name} / {formatAgeFromHours(signal.freshness_age_hours)}
                </small>
              </div>
            </article>
          ))}
          {signals.length === 0 ? <p>No related signals in current filters.</p> : null}
        </div>
      </section>

      <section className="wr-related-signals">
        <h3>NEARBY OPERATORS</h3>
        <div>
          {nearbyOperators.slice(0, 3).map((nearby) => (
            <article key={nearby.id}>
              <span />
              <div>
                <strong>{nearby.name}</strong>
                <small>{nearby.status} / same neighborhood</small>
              </div>
            </article>
          ))}
          {nearbyOperators.length === 0 ? <p>No same-area operators in the current view.</p> : null}
        </div>
      </section>
    </aside>
  );
}

function ContactMini({ contact }: { contact: ContactMethod }) {
  const href = contactHref(contact);
  return (
    <article>
      <span>{contactIcon(contact)}</span>
      <div>
        <strong>
          <a href={href} target={href.startsWith("http") ? "_blank" : undefined} rel="noreferrer">
            {contact.value}
          </a>
        </strong>
        <small>
          {contact.platform ?? contact.type} /{" "}
          {contact.source_ref.url ? (
            <a href={contact.source_ref.url} target="_blank" rel="noreferrer">
              source
            </a>
          ) : (
            contact.source_ref.source_name
          )}
        </small>
      </div>
    </article>
  );
}

function contactIcon(contact: ContactMethod) {
  if (contact.type === "phone") {
    return <Phone size={12} />;
  }
  if (contact.type === "email") {
    return <Mail size={12} />;
  }
  if (contact.type === "social") {
    return <AtSign size={12} />;
  }
  return <Globe2 size={12} />;
}

function contactHref(contact: ContactMethod): string {
  if (contact.type === "phone") {
    return `tel:${contact.value.replace(/[^0-9+]/g, "")}`;
  }
  if (contact.type === "email") {
    return `mailto:${contact.value}`;
  }
  return contact.value;
}

function MetricTile({
  label,
  value,
  tone = "neutral"
}: {
  label: string;
  value: string;
  tone?: "neutral" | "opportunity" | "signal";
}) {
  return (
    <div className={`wr-inspector-metric wr-metric-${tone}`}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}
