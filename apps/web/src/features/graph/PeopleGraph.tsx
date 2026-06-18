import Graph from "graphology";
import louvain from "graphology-communities-louvain";
import FA2Layout from "graphology-layout-forceatlas2/worker";
import { Network } from "lucide-react";
import { useEffect, useRef } from "react";
import Sigma from "sigma";
import type { GraphEdge, GraphNode } from "../../lib/api";
import { entity, text } from "../../lib/theme";

type Props = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string) => void;
};

const COMMUNITY_COLORS = [entity.operator, entity.people, entity.opportunity, entity.signal];

export function PeopleGraph({ nodes, edges, selectedNodeId, onSelectNode }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current || nodes.length === 0) {
      return;
    }
    const graph = new Graph({ type: "undirected", multi: false });
    for (const [index, node] of nodes.entries()) {
      const fallback = fallbackPosition(index, nodes.length);
      const showLabel = node.centrality >= highCentralityThreshold(nodes);
      graph.addNode(node.id, {
        label: showLabel ? node.label : "",
        x: node.x ?? fallback.x,
        y: node.y ?? fallback.y,
        size: 5 + node.centrality * 14,
        color: colorFor(node.community),
        nodeType: node.node_type,
        community: node.community,
        centrality: node.centrality,
        sourceNodeId: node.id
      });
    }
    for (const edge of edges) {
      if (!graph.hasNode(edge.source) || !graph.hasNode(edge.target)) {
        continue;
      }
      graph.mergeEdgeWithKey(edge.id, edge.source, edge.target, {
        label: edge.edge_type,
        size: Math.max(edge.weight * 1.6, 0.8),
        color: "rgba(43,58,77,.72)"
      });
    }
    if (graph.order > 0 && graph.size > 0) {
      louvain.assign(graph, { nodeCommunityAttribute: "community" });
      const maxDegree = Math.max(...graph.nodes().map((node) => graph.degree(node)), 1);
      graph.forEachNode((node) => {
        const centrality = graph.degree(node) / maxDegree;
        const community = Number(graph.getNodeAttribute(node, "community") ?? 0);
        graph.mergeNodeAttributes(node, {
          size: Math.max(Number(graph.getNodeAttribute(node, "size") ?? 5), 5 + centrality * 11),
          color: colorFor(community)
        });
      });
    }
    const renderer = new Sigma(graph, containerRef.current, {
      allowInvalidContainer: true,
      defaultEdgeColor: "rgba(43,58,77,.72)",
      defaultNodeColor: entity.people,
      labelColor: { color: text.primary },
      labelDensity: 0.08,
      labelRenderedSizeThreshold: 10,
      renderEdgeLabels: false
    });
    renderer.on("clickNode", (event) => {
      const nodeId = String(graph.getNodeAttribute(event.node, "sourceNodeId") ?? event.node);
      onSelectNode(nodeId);
    });
    const layout = graph.size > 0 ? new FA2Layout(graph, { settings: { gravity: 1 } }) : null;
    layout?.start();
    const timer = window.setTimeout(() => layout?.stop(), 1600);
    return () => {
      window.clearTimeout(timer);
      layout?.kill();
      renderer.kill();
      graph.clear();
    };
  }, [nodes, edges, onSelectNode]);

  return (
    <section className="wr-people-graph" aria-label="People graph">
      <div className="wr-people-graph-canvas" ref={containerRef}>
        {nodes.length === 0 ? (
          <p className="emptyInline">
            <Network size={14} /> Run the M3 graph job.
          </p>
        ) : null}
      </div>
      <div className="wr-people-title">
        <h1>Relationship Graph</h1>
        <span>public professional data only / Louvain communities / centrality sizing</span>
      </div>
      <div className="wr-community-legend">
        <strong>COMMUNITIES</strong>
        <div>
          <span>
            <i style={{ background: entity.operator }} /> operators
          </span>
          <span>
            <i style={{ background: entity.people }} /> people
          </span>
          <span>
            <i style={{ background: entity.opportunity }} /> press
          </span>
          <span>
            <i style={{ background: entity.signal }} /> civic / regulatory
          </span>
        </div>
        <p>node size = centrality / public professional data only / no patient, clinical, social or LinkedIn</p>
      </div>
      {selectedNodeId ? <div className="wr-graph-selection" aria-hidden /> : null}
    </section>
  );
}

function colorFor(community: number): string {
  return COMMUNITY_COLORS[Math.abs(community) % COMMUNITY_COLORS.length];
}

function fallbackPosition(index: number, count: number): { x: number; y: number } {
  const angle = (index / Math.max(count, 1)) * Math.PI * 2;
  const radius = 1 + (index % 5) * 0.08;
  return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius };
}

function highCentralityThreshold(nodes: GraphNode[]): number {
  const sorted = nodes.map((node) => node.centrality).sort((a, b) => b - a);
  return sorted[Math.min(6, sorted.length - 1)] ?? 0.35;
}
