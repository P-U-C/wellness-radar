from __future__ import annotations

import math
from collections import defaultdict, deque
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from psycopg.types.json import Jsonb

from apps.jobs.runner import DatabaseRepository, RunMetrics
from packages.shared.ids import stable_id
from packages.shared.normalizers import normalize_name


@dataclass(frozen=True)
class GraphNode:
    id: str
    node_type: str
    entity_id: str
    label: str
    primary_category: str | None
    source_refs: list[dict[str, Any]]
    confidence_score: float
    payload: dict[str, Any]


@dataclass(frozen=True)
class GraphEdge:
    id: str
    source_node_id: str
    target_node_id: str
    edge_type: str
    weight: float
    source_refs: list[dict[str, Any]]
    confidence_score: float
    payload: dict[str, Any]


class GraphRepository(DatabaseRepository):
    def people(self) -> list[dict[str, Any]]:
        return list(
            self.conn.execute(
                """
                SELECT id, name, roles, affiliations, source_refs, confidence_score
                FROM person
                WHERE jsonb_array_length(source_refs) > 0
                """
            ).fetchall()
        )

    def organizations(self) -> list[dict[str, Any]]:
        return list(
            self.conn.execute(
                """
                SELECT id, name, normalized_name, source_refs, confidence_score
                FROM organization
                WHERE jsonb_array_length(source_refs) > 0
                """
            ).fetchall()
        )

    def operators(self) -> list[dict[str, Any]]:
        return list(
            self.conn.execute(
                """
                SELECT
                  id,
                  name,
                  normalized_name,
                  organization_id,
                  categories,
                  source_refs,
                  confidence_score
                FROM "operator"
                WHERE jsonb_array_length(source_refs) > 0
                  -- Keep public-recreation facilities (parks, courts, rinks) out of the
                  -- people/org graph: they have no people behind them and otherwise flood
                  -- the graph and can surface as a top-centrality "person".
                  AND COALESCE(venue_class, '') <> 'public_recreation'
                """
            ).fetchall()
        )

    def events(self) -> list[dict[str, Any]]:
        return list(
            self.conn.execute(
                """
                SELECT id, title, host_org_id, topics, source_refs
                FROM event
                WHERE jsonb_array_length(source_refs) > 0
                """
            ).fetchall()
        )

    def replace_graph(
        self,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
        centrality: dict[str, float],
        communities: dict[str, int],
        positions: dict[str, tuple[float, float]],
    ) -> None:
        self.conn.execute("DELETE FROM entity_graph_edge")
        self.conn.execute("DELETE FROM entity_graph_node")
        for node in nodes:
            x, y = positions[node.id]
            self.conn.execute(
                """
                INSERT INTO entity_graph_node (
                  id,
                  node_type,
                  entity_id,
                  label,
                  primary_category,
                  centrality,
                  community,
                  x,
                  y,
                  source_refs,
                  confidence_score,
                  payload
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    node.id,
                    node.node_type,
                    node.entity_id,
                    node.label,
                    node.primary_category,
                    centrality.get(node.id, 0.0),
                    communities.get(node.id, 0),
                    x,
                    y,
                    Jsonb(node.source_refs),
                    node.confidence_score,
                    Jsonb(node.payload),
                ),
            )
        for edge in edges:
            self.conn.execute(
                """
                INSERT INTO entity_graph_edge (
                  id,
                  source_node_id,
                  target_node_id,
                  edge_type,
                  weight,
                  source_refs,
                  confidence_score,
                  payload
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_node_id, target_node_id, edge_type) DO UPDATE SET
                  weight = EXCLUDED.weight,
                  source_refs = EXCLUDED.source_refs,
                  confidence_score = EXCLUDED.confidence_score,
                  payload = EXCLUDED.payload,
                  updated_at = now()
                """,
                (
                    edge.id,
                    edge.source_node_id,
                    edge.target_node_id,
                    edge.edge_type,
                    edge.weight,
                    Jsonb(edge.source_refs),
                    edge.confidence_score,
                    Jsonb(edge.payload),
                ),
            )


def run_graph_build(repository: GraphRepository | None = None) -> RunMetrics:
    repo = repository or GraphRepository()
    metrics = RunMetrics()
    try:
        people = repo.people()
        organizations = repo.organizations()
        operators = repo.operators()
        events = repo.events()
        nodes, edges = build_graph_rows(people, organizations, operators, events)
        centrality = degree_centrality(nodes, edges)
        communities = connected_component_communities(nodes, edges)
        positions = radial_positions(nodes, communities)
        repo.replace_graph(nodes, edges, centrality, communities, positions)
        metrics.records_fetched = len(people) + len(organizations) + len(operators) + len(events)
        metrics.records_persisted = len(nodes) + len(edges)
        return metrics
    finally:
        repo.close()


def build_graph_rows(
    people: list[dict[str, Any]],
    organizations: list[dict[str, Any]],
    operators: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> tuple[list[GraphNode], list[GraphEdge]]:
    nodes: dict[str, GraphNode] = {}
    edges: dict[str, GraphEdge] = {}
    org_by_name = {normalize_name(str(org["name"])): org for org in organizations}
    op_by_name = {normalize_name(str(operator["name"])): operator for operator in operators}
    op_by_id = {str(operator["id"]): operator for operator in operators}

    for person in people:
        node = _person_node(
            person,
            _person_categories(
                person,
                operators=operators,
                op_by_id=op_by_id,
                op_by_name=op_by_name,
            ),
        )
        nodes[node.id] = node
    for org in organizations:
        node = _organization_node(
            org,
            _organization_categories(org, operators=operators, op_by_name=op_by_name),
        )
        nodes[node.id] = node
    for operator in operators:
        node = _operator_node(operator)
        nodes[node.id] = node
    for event in events:
        node = _event_node(event)
        nodes[node.id] = node

    for operator in operators:
        if operator.get("organization_id"):
            edge = _edge(
                source_node_id=f"node_operator_{operator['id']}",
                target_node_id=f"node_organization_{operator['organization_id']}",
                edge_type="mentioned_with",
                source_refs=operator["source_refs"],
                confidence_score=float(operator["confidence_score"]),
                weight=0.9,
                payload={
                    "operator_id": operator["id"],
                    "organization_id": operator["organization_id"],
                },
            )
            edges[edge.id] = edge

    for person in people:
        person_node_id = f"node_person_{person['id']}"
        for affiliation in person["affiliations"]:
            affiliation_name = normalize_name(str(affiliation.get("organization_name") or ""))
            if not affiliation_name:
                continue
            if affiliation_name in org_by_name:
                org = org_by_name[affiliation_name]
                edge_type = _affiliation_edge_type(str(affiliation.get("role") or ""))
                edge = _edge(
                    source_node_id=person_node_id,
                    target_node_id=f"node_organization_{org['id']}",
                    edge_type=edge_type,
                    source_refs=_unique_refs([*person["source_refs"], *org["source_refs"]]),
                    confidence_score=min(
                        float(person["confidence_score"]),
                        float(org["confidence_score"]),
                    ),
                    weight=0.8,
                    payload={"affiliation": affiliation},
                )
                edges[edge.id] = edge
            if affiliation_name in op_by_name:
                operator = op_by_name[affiliation_name]
                edge = _edge(
                    source_node_id=person_node_id,
                    target_node_id=f"node_operator_{operator['id']}",
                    edge_type=_affiliation_edge_type(str(affiliation.get("role") or "")),
                    source_refs=_unique_refs([*person["source_refs"], *operator["source_refs"]]),
                    confidence_score=min(
                        float(person["confidence_score"]),
                        float(operator["confidence_score"]),
                    ),
                    weight=0.85,
                    payload={"affiliation": affiliation},
                )
                edges[edge.id] = edge

    for event in events:
        if event.get("host_org_id"):
            edge = _edge(
                source_node_id=f"node_event_{event['id']}",
                target_node_id=f"node_organization_{event['host_org_id']}",
                edge_type="speaker",
                source_refs=event["source_refs"],
                confidence_score=0.75,
                weight=0.65,
                payload={"event_id": event["id"], "host_org_id": event["host_org_id"]},
            )
            edges[edge.id] = edge

    return list(nodes.values()), list(edges.values())


def degree_centrality(nodes: list[GraphNode], edges: list[GraphEdge]) -> dict[str, float]:
    degree: dict[str, int] = {node.id: 0 for node in nodes}
    for edge in edges:
        degree[edge.source_node_id] = degree.get(edge.source_node_id, 0) + 1
        degree[edge.target_node_id] = degree.get(edge.target_node_id, 0) + 1
    max_degree = max(degree.values(), default=1)
    return {node_id: round(count / max(max_degree, 1), 4) for node_id, count in degree.items()}


def connected_component_communities(
    nodes: list[GraphNode], edges: list[GraphEdge]
) -> dict[str, int]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for node in nodes:
        adjacency[node.id]
    for edge in edges:
        adjacency[edge.source_node_id].add(edge.target_node_id)
        adjacency[edge.target_node_id].add(edge.source_node_id)
    communities: dict[str, int] = {}
    current = 0
    for node in nodes:
        if node.id in communities:
            continue
        current += 1
        queue: deque[str] = deque([node.id])
        while queue:
            item = queue.popleft()
            if item in communities:
                continue
            communities[item] = current
            queue.extend(neighbor for neighbor in adjacency[item] if neighbor not in communities)
    return communities


def radial_positions(
    nodes: list[GraphNode], communities: dict[str, int]
) -> dict[str, tuple[float, float]]:
    positions: dict[str, tuple[float, float]] = {}
    community_counts: dict[int, int] = defaultdict(int)
    for index, node in enumerate(nodes):
        community = communities.get(node.id, 0)
        local_index = community_counts[community]
        community_counts[community] += 1
        angle = (index * 2.399963229728653) + local_index
        radius = 1 + community * 0.6 + local_index * 0.08
        positions[node.id] = (
            round(math.cos(angle) * radius, 4),
            round(math.sin(angle) * radius, 4),
        )
    return positions


def _person_node(person: dict[str, Any], categories: list[str] | None = None) -> GraphNode:
    categories = categories or []
    return GraphNode(
        id=f"node_person_{person['id']}",
        node_type="person",
        entity_id=str(person["id"]),
        label=str(person["name"]),
        primary_category=categories[0] if categories else None,
        source_refs=person["source_refs"],
        confidence_score=float(person["confidence_score"]),
        payload={
            "roles": person["roles"],
            "affiliations": person["affiliations"],
            "categories": categories,
        },
    )


def _organization_node(org: dict[str, Any], categories: list[str] | None = None) -> GraphNode:
    categories = categories or []
    return GraphNode(
        id=f"node_organization_{org['id']}",
        node_type="organization",
        entity_id=str(org["id"]),
        label=str(org["name"]),
        primary_category=categories[0] if categories else None,
        source_refs=org["source_refs"],
        confidence_score=float(org["confidence_score"]),
        payload={"categories": categories},
    )


def _operator_node(operator: dict[str, Any]) -> GraphNode:
    categories = list(operator["categories"])
    return GraphNode(
        id=f"node_operator_{operator['id']}",
        node_type="operator",
        entity_id=str(operator["id"]),
        label=str(operator["name"]),
        primary_category=categories[0] if categories else None,
        source_refs=operator["source_refs"],
        confidence_score=float(operator["confidence_score"]),
        payload={"categories": categories, "organization_id": operator.get("organization_id")},
    )


def _event_node(event: dict[str, Any]) -> GraphNode:
    topics = list(event["topics"])
    return GraphNode(
        id=f"node_event_{event['id']}",
        node_type="event",
        entity_id=str(event["id"]),
        label=str(event["title"]),
        primary_category=topics[0] if topics else None,
        source_refs=event["source_refs"],
        confidence_score=0.75,
        payload={"topics": topics, "host_org_id": event.get("host_org_id")},
    )


def _edge(
    *,
    source_node_id: str,
    target_node_id: str,
    edge_type: str,
    source_refs: list[dict[str, Any]],
    confidence_score: float,
    weight: float,
    payload: dict[str, Any],
) -> GraphEdge:
    return GraphEdge(
        id=stable_id("edge", source_node_id, target_node_id, edge_type),
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        edge_type=edge_type,
        weight=weight,
        source_refs=source_refs,
        confidence_score=confidence_score,
        payload=payload,
    )


def _affiliation_edge_type(role: str) -> str:
    lowered = role.lower()
    if "advisor" in lowered:
        return "advisor"
    if "investor" in lowered:
        return "investor"
    if "founder" in lowered:
        return "founder"
    return "employee"


def _person_categories(
    person: dict[str, Any],
    *,
    operators: list[dict[str, Any]],
    op_by_id: dict[str, dict[str, Any]],
    op_by_name: dict[str, dict[str, Any]],
) -> list[str]:
    matches: list[dict[str, Any]] = []
    for affiliation in person.get("affiliations") or []:
        if not isinstance(affiliation, dict):
            continue
        operator_id = str(affiliation.get("operator_id") or "")
        if operator_id and operator_id in op_by_id:
            matches.append(op_by_id[operator_id])
            continue
        for key in ("operator_name", "organization_name"):
            match = _operator_match_for_name(
                affiliation.get(key),
                operators=operators,
                op_by_name=op_by_name,
            )
            if match is not None:
                matches.append(match)
                break
    return _categories_from_operator_matches(matches)


def _organization_categories(
    org: dict[str, Any],
    *,
    operators: list[dict[str, Any]],
    op_by_name: dict[str, dict[str, Any]],
) -> list[str]:
    matches = [
        operator
        for operator in operators
        if operator.get("organization_id") and operator.get("organization_id") == org.get("id")
    ]
    name_match = _operator_match_for_name(
        org.get("name"),
        operators=operators,
        op_by_name=op_by_name,
    )
    if name_match is not None:
        matches.append(name_match)
    return _categories_from_operator_matches(matches)


def _operator_match_for_name(
    value: Any,
    *,
    operators: list[dict[str, Any]],
    op_by_name: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    normalized = normalize_name(str(value or ""))
    if not normalized:
        return None
    exact = op_by_name.get(normalized)
    if exact is not None:
        return exact
    if len(normalized) < 6:
        return None
    for operator in operators:
        operator_name = str(operator.get("normalized_name") or "")
        if not operator_name:
            operator_name = normalize_name(str(operator.get("name") or ""))
        if operator_name.startswith(normalized) or normalized.startswith(operator_name):
            return operator
    return None


def _categories_from_operator_matches(matches: Iterable[dict[str, Any]]) -> list[str]:
    categories: list[str] = []
    seen: set[str] = set()
    for operator in matches:
        for category in operator.get("categories") or []:
            category_text = str(category)
            if category_text in seen:
                continue
            seen.add(category_text)
            categories.append(category_text)
    return categories


def _unique_refs(refs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for ref in refs:
        key = "|".join(str(ref.get(field)) for field in ("source_name", "url", "source_record_id"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(ref)
    return unique
