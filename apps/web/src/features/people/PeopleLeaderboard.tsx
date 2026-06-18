import { Flag, Link2 } from "lucide-react";
import { ProvenanceBlock } from "../../components";
import type { GraphNode, Operator, Person } from "../../lib/api";
import { formatScore, sentenceCase } from "../../lib/format";
import { magma } from "../../lib/theme";

type Props = {
  people: Person[];
  operators: Operator[];
  graphNodes: GraphNode[];
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string) => void;
  onOpenOperator: (operatorId: string) => void;
};

export function PeopleLeaderboard({
  people,
  operators,
  graphNodes,
  selectedNodeId,
  onSelectNode,
  onOpenOperator
}: Props) {
  const selectedNode = graphNodes.find((node) => node.id === selectedNodeId) ?? topGraphNode(graphNodes);
  const person = selectedNode ? findPerson(selectedNode, people) : topPerson(people);
  const linkedOperator = selectedNode ? findLinkedOperator(selectedNode, person, operators) : null;
  const influence = influenceScore(person, selectedNode);
  const sourceRefs = person?.influence_source_refs?.length ? person.influence_source_refs : person?.source_refs ?? selectedNode?.source_refs ?? [];
  const confidence =
    person?.influence_source_confidence ?? person?.confidence_score ?? selectedNode?.confidence_score ?? 0;

  return (
    <aside className="wr-people-inspector" aria-label="People inspector">
      {person || selectedNode ? (
        <>
          <header className="wr-person-head">
            <div className="wr-person-avatar" aria-hidden>
              {initials(person?.name ?? selectedNode?.label ?? "WR")}
            </div>
            <div>
              <span>
                <i /> PERSON / {sentenceCase(selectedNode?.node_type ?? "public professional")}
              </span>
              <h2>{person?.name ?? selectedNode?.label ?? "Public professional"}</h2>
            </div>
          </header>
          <p className="wr-person-role">
            {person?.primary_role ?? selectedNode?.primary_category ?? "Public professional"} /{" "}
            {person?.primary_affiliation ?? "source-backed public record"}
          </p>

          <section className="wr-influence-card">
            <div>
              <span>INFLUENCE SCORE</span>
              <strong>{formatScore(influence)}</strong>
            </div>
            <ComponentBar label="centrality" value={selectedNode?.centrality ?? componentValue(person, "network_centrality")} />
            <ComponentBar label="reach" value={componentValue(person, "institutional_authority") ?? influence} />
            <ComponentBar label="recency" value={componentValue(person, "source_confidence") ?? confidence} />
          </section>

          <section className="wr-why-card">
            <h3>WHY THIS PERSON APPEARS</h3>
            <p>
              {person?.influence_explanation ??
                fallbackExplanation(selectedNode, linkedOperator)}{" "}
              Score is explainable and reversible; <span>correction requests</span> are auditable.
            </p>
          </section>

          <ProvenanceBlock
            source_refs={sourceRefs}
            confidence_score={confidence}
            freshness_age_hours={person?.freshness_age_hours}
            compact
          />

          <div className="wr-person-actions">
            <button
              type="button"
              disabled={!linkedOperator}
              onClick={() => linkedOperator && onOpenOperator(linkedOperator.id)}
            >
              <Link2 size={14} /> {linkedOperator ? "Linked operator" : "No linked operator"}
            </button>
            <button type="button">
              <Flag size={14} /> Flag
            </button>
          </div>

          <section className="wr-public-list" aria-label="High influence public records">
            <h3>PUBLIC RECORDS</h3>
            {graphNodes.slice(0, 5).map((node) => (
              <button
                key={node.id}
                className={node.id === selectedNode?.id ? "is-active" : ""}
                type="button"
                onClick={() => onSelectNode(node.id)}
              >
                <span>{node.label}</span>
                <b style={{ color: magma(node.centrality) }}>{formatScore(node.centrality)}</b>
              </button>
            ))}
          </section>
        </>
      ) : (
        <p className="wr-feed-state">No public professional graph records are available.</p>
      )}
    </aside>
  );
}

function ComponentBar({ label, value }: { label: string; value: number | null }) {
  const normalized = Math.max(0, Math.min(1, value ?? 0));
  return (
    <div className="wr-component-bar">
      <span>{label}</span>
      <div aria-hidden>
        <i style={{ width: `${normalized * 100}%` }} />
      </div>
      <b>{value === null ? "n/a" : formatScore(normalized)}</b>
    </div>
  );
}

function topGraphNode(nodes: GraphNode[]): GraphNode | null {
  return [...nodes].sort((a, b) => b.centrality - a.centrality)[0] ?? null;
}

function topPerson(people: Person[]): Person | null {
  return (
    [...people].sort(
      (a, b) => (b.influence_score ?? b.confidence_score) - (a.influence_score ?? a.confidence_score)
    )[0] ?? null
  );
}

function findPerson(node: GraphNode, people: Person[]): Person | null {
  if (node.node_type === "person") {
    return people.find((person) => person.id === node.entity_id || person.id === node.id) ?? null;
  }
  const label = node.label.toLowerCase();
  return people.find((person) => person.name.toLowerCase() === label) ?? null;
}

function findLinkedOperator(node: GraphNode, person: Person | null, operators: Operator[]): Operator | null {
  if (node.node_type === "operator") {
    return operators.find((operator) => operator.id === node.entity_id || operator.id === node.id) ?? null;
  }
  const affiliation = person?.primary_affiliation?.toLowerCase();
  if (!affiliation) {
    return null;
  }
  return operators.find((operator) => affiliation.includes(operator.name.toLowerCase())) ?? null;
}

function influenceScore(person: Person | null, node: GraphNode | null): number {
  return person?.influence_score ?? node?.centrality ?? person?.confidence_score ?? 0;
}

function componentValue(person: Person | null, key: string): number | null {
  const value = person?.influence_components?.[key];
  return typeof value === "number" ? value : null;
}

function fallbackExplanation(node: GraphNode | null, operator: Operator | null): string {
  if (!node) {
    return "The record is present in the public professional graph with source-backed provenance.";
  }
  const operatorText = operator ? ` and links to ${operator.name}` : "";
  return `${node.label} appears because it has public professional graph relationships${operatorText}.`;
}

function initials(value: string): string {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}
