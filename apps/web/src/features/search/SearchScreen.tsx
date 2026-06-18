import { Search } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { SourceChip } from "../../components";
import type { Operator, OpportunityScorecard, Person, Signal, SourceRef } from "../../lib/api";
import { formatAgeFromHours, formatScore, sentenceCase } from "../../lib/format";
import { entity, magma } from "../../lib/theme";

type SearchType = "all" | "operators" | "signals" | "people" | "opportunity";

type Props = {
  operators: Operator[];
  signals: Signal[];
  people: Person[];
  scorecards: OpportunityScorecard[];
  onOpenOperator: (operatorId: string) => void;
  onOpenSignal: (signal: Signal) => void;
  onOpenPerson: (personId: string) => void;
  onOpenOpportunity: () => void;
};

export function SearchScreen({
  operators,
  signals,
  people,
  scorecards,
  onOpenOperator,
  onOpenSignal,
  onOpenPerson,
  onOpenOpportunity
}: Props) {
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<SearchType>("all");
  const inputRef = useRef<HTMLInputElement | null>(null);
  const results = useMemo(
    () => ({
      operators: operators.filter((operator) => matchesOperator(operator, query)).slice(0, 8),
      signals: signals.filter((signal) => matchesSignal(signal, query)).slice(0, 8),
      people: people.filter((person) => matchesPerson(person, query)).slice(0, 8),
      opportunity: scorecards.filter((scorecard) => matchesOpportunity(scorecard, query)).slice(0, 8)
    }),
    [operators, people, query, scorecards, signals]
  );
  const counts = {
    operators: results.operators.length,
    signals: results.signals.length,
    people: results.people.length,
    opportunity: results.opportunity.length
  };
  const totalCount = counts.operators + counts.signals + counts.people + counts.opportunity;

  useEffect(() => {
    inputRef.current?.focus();
    function focusSearch() {
      inputRef.current?.focus();
    }
    window.addEventListener("wr-focus-search", focusSearch);
    return () => window.removeEventListener("wr-focus-search", focusSearch);
  }, []);

  return (
    <section className="wr-search-screen" aria-label="Cross-object search">
      <div className="wr-search-inner">
        <div>
          <label className="wr-search-bar">
            <Search size={18} />
            <input
              ref={inputRef}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search operators, signals, people, opportunity"
              aria-label="Search ontology"
            />
            <span aria-hidden />
            <kbd>esc</kbd>
          </label>
          <div className="wr-search-pills" aria-label="Entity type filter">
            <TypePill label="All" type="all" count={totalCount} active={typeFilter === "all"} onClick={setTypeFilter} />
            <TypePill
              label="Operators"
              type="operators"
              count={counts.operators}
              active={typeFilter === "operators"}
              onClick={setTypeFilter}
            />
            <TypePill
              label="Signals"
              type="signals"
              count={counts.signals}
              active={typeFilter === "signals"}
              onClick={setTypeFilter}
            />
            <TypePill
              label="People"
              type="people"
              count={counts.people}
              active={typeFilter === "people"}
              onClick={setTypeFilter}
            />
            <TypePill
              label="Opportunity"
              type="opportunity"
              count={counts.opportunity}
              active={typeFilter === "opportunity"}
              onClick={setTypeFilter}
            />
          </div>
        </div>

        {(typeFilter === "all" || typeFilter === "operators") && (
          <ResultGroup label="OPERATORS" color={entity.operator}>
            {results.operators.map((operator) => (
              <ResultRow
                key={operator.id}
                title={operator.name}
                badge={operator.status}
                subtitle={`${operator.categories.map(sentenceCase).slice(0, 2).join(" / ")} / ${
                  operator.address ?? operator.neighborhood ?? "Metro Vancouver"
                }`}
                sourceRefs={operator.source_refs}
                confidence={operator.confidence_score}
                ageHours={operator.freshness_age_hours}
                onClick={() => onOpenOperator(operator.id)}
              />
            ))}
          </ResultGroup>
        )}

        {(typeFilter === "all" || typeFilter === "signals") && (
          <ResultGroup label="SIGNALS" color={entity.signal}>
            {results.signals.map((signal) => (
              <ResultRow
                key={signal.id}
                title={signal.title}
                badge={signal.type}
                subtitle={`${sentenceCase(signal.severity)} / ${signal.summary ?? "source-backed signal"}`}
                sourceRefs={signal.source_refs}
                confidence={signal.confidence_score}
                ageHours={signal.freshness_age_hours}
                onClick={() => onOpenSignal(signal)}
              />
            ))}
          </ResultGroup>
        )}

        {(typeFilter === "all" || typeFilter === "people") && (
          <ResultGroup label="PEOPLE" color={entity.people}>
            {results.people.map((person) => (
              <ResultRow
                key={person.id}
                title={person.name}
                badge={person.primary_role ?? "person"}
                subtitle={`${person.primary_affiliation ?? "public professional"} / ${
                  person.influence_explanation ?? "source-backed public record"
                }`}
                sourceRefs={person.source_refs}
                confidence={person.confidence_score}
                ageHours={person.freshness_age_hours}
                onClick={() => onOpenPerson(person.id)}
              />
            ))}
          </ResultGroup>
        )}

        {(typeFilter === "all" || typeFilter === "opportunity") && (
          <ResultGroup label="OPPORTUNITY" color={entity.opportunity}>
            {results.opportunity.map((scorecard) => (
              <ResultRow
                key={scorecard.id}
                title={`${scorecard.geo_name} / ${sentenceCase(scorecard.category)}`}
                badge={formatScore(scorecard.opportunity_score)}
                subtitle={`score ${formatScore(scorecard.opportunity_score)} / ${scorecard.caveat}`}
                sourceRefs={scorecard.source_refs}
                confidence={scorecard.confidence_score}
                ageHours={scorecard.freshness_age_hours}
                onClick={onOpenOpportunity}
              />
            ))}
          </ResultGroup>
        )}
      </div>
    </section>
  );
}

function TypePill({
  label,
  type,
  count,
  active,
  onClick
}: {
  label: string;
  type: SearchType;
  count: number;
  active: boolean;
  onClick: (type: SearchType) => void;
}) {
  return (
    <button className={`wr-search-pill wr-search-pill-${type}${active ? " is-active" : ""}`} type="button" onClick={() => onClick(type)}>
      {label} <span>{count}</span>
    </button>
  );
}

function ResultGroup({ label, color, children }: { label: string; color: string; children: ReactNode }) {
  return (
    <section className="wr-result-group">
      <div className="wr-result-heading">
        <i style={{ background: color }} />
        <span>{label}</span>
        <b />
      </div>
      <div className="wr-result-rows">{children}</div>
    </section>
  );
}

function ResultRow({
  title,
  badge,
  subtitle,
  sourceRefs,
  confidence,
  ageHours,
  onClick
}: {
  title: string;
  badge: string;
  subtitle: string;
  sourceRefs: SourceRef[];
  confidence: number;
  ageHours?: number | null;
  onClick: () => void;
}) {
  const source = sourceRefs[0];
  return (
    <button className="wr-result-row" type="button" onClick={onClick}>
      <span>
        <strong>
          {title}
          <b>{sentenceCase(badge)}</b>
        </strong>
        <small>{subtitle}</small>
      </span>
      <span>
        {source ? <SourceChip refData={source} compact disableLink /> : <em>No source</em>}
        <small>
          conf <b style={{ color: magma(confidence) }}>{formatScore(confidence)}</b> / {formatAgeFromHours(ageHours)}
        </small>
      </span>
    </button>
  );
}

function matchesOperator(operator: Operator, query: string): boolean {
  return matches(
    [operator.name, operator.address, operator.neighborhood, operator.municipality, operator.status, ...operator.categories],
    query
  );
}

function matchesSignal(signal: Signal, query: string): boolean {
  return matches([signal.title, signal.summary, signal.why_it_matters, signal.type, signal.severity, signal.source_name], query);
}

function matchesPerson(person: Person, query: string): boolean {
  return matches([person.name, person.primary_role, person.primary_affiliation, person.influence_explanation], query);
}

function matchesOpportunity(scorecard: OpportunityScorecard, query: string): boolean {
  return matches([scorecard.geo_name, scorecard.category, scorecard.caveat, scorecard.calculation_method], query);
}

function matches(values: Array<string | null | undefined>, query: string): boolean {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  return values.some((value) => value?.toLowerCase().includes(normalized));
}
