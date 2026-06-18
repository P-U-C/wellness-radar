import { ArrowDownAZ, BadgeCheck } from "lucide-react";
import type { Person } from "../../lib/api";

type Props = {
  people: Person[];
  sort: string;
  onSortChange: (sort: string) => void;
};

export function PeopleLeaderboard({ people, sort, onSortChange }: Props) {
  return (
    <section className="sideSection" aria-label="People leaderboard">
      <div className="sectionHeader">
        <h2>People</h2>
        <select
          aria-label="People sort"
          value={sort}
          onChange={(event) => onSortChange(event.target.value)}
        >
          <option value="influence">Influence</option>
          <option value="confidence">Confidence</option>
          <option value="name">Name</option>
          <option value="role">Role</option>
        </select>
      </div>
      <div className="peopleList">
        {people.slice(0, 8).map((person) => (
          <article key={person.id} className="personRow">
            <div>
              <strong>{person.name}</strong>
              <span>{person.primary_role ?? "Public professional"}</span>
              <small>{person.primary_affiliation ?? "Source-backed public record"}</small>
              {person.influence_explanation ? <small>{person.influence_explanation}</small> : null}
              <small>
                {person.source_refs.length} refs · {formatFreshness(person.freshness_age_hours)}
              </small>
              {person.influence_components ? (
                <div className="miniComponents">
                  <span>authority {formatPercent(person.influence_components.institutional_authority)}</span>
                  <span>network {formatPercent(person.influence_components.network_centrality)}</span>
                  <span>confidence {formatPercent(person.influence_components.source_confidence)}</span>
                </div>
              ) : null}
            </div>
            <span className="confidencePill">
              <BadgeCheck size={13} />
              {person.influence_score !== null
                ? `${Math.round(person.influence_score * 100)}%`
                : `${Math.round(person.confidence_score * 100)}%`}
            </span>
          </article>
        ))}
        {people.length === 0 ? (
          <p className="emptyInline">
            <ArrowDownAZ size={14} /> No public-professional seed records loaded.
          </p>
        ) : null}
      </div>
    </section>
  );
}

function formatPercent(value: unknown): string {
  if (typeof value !== "number") {
    return "-";
  }
  return `${Math.round(value * 100)}`;
}

function formatFreshness(ageHours?: number | null): string {
  if (ageHours === null || ageHours === undefined) {
    return "freshness n/a";
  }
  if (ageHours < 1) {
    return "updated <1h";
  }
  if (ageHours < 48) {
    return `updated ${Math.round(ageHours)}h`;
  }
  return `updated ${Math.round(ageHours / 24)}d`;
}
