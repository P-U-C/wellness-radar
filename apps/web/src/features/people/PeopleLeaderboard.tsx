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
              <small>{person.primary_affiliation ?? "Affiliation pending"}</small>
            </div>
            <span className="confidencePill">
              <BadgeCheck size={13} />
              {Math.round(person.confidence_score * 100)}%
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
