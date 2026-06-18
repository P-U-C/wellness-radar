import Graph from "graphology";
import louvain from "graphology-communities-louvain";
import FA2Layout from "graphology-layout-forceatlas2/worker";
import { Network } from "lucide-react";
import { useEffect, useRef } from "react";
import Sigma from "sigma";
import type { GraphEdge, GraphNode } from "../../lib/api";

type Props = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};

const COMMUNITY_COLORS = ["#2bd4a7", "#f2c94c", "#7dd3fc", "#ff6b6b", "#c084fc", "#f59e0b"];

export function PeopleGraph({ nodes, edges }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current || nodes.length === 0) {
      return;
    }
    const graph = new Graph({ type: "undirected", multi: false });
    for (const [index, node] of nodes.entries()) {
      graph.addNode(node.id, {
        label: node.label,
        x: node.x ?? Math.cos(index),
        y: node.y ?? Math.sin(index),
        size: 4 + node.centrality * 8,
        color: colorFor(node.community),
        nodeType: node.node_type,
        community: node.community
      });
    }
    for (const edge of edges) {
      if (!graph.hasNode(edge.source) || !graph.hasNode(edge.target)) {
        continue;
      }
      graph.mergeEdgeWithKey(edge.id, edge.source, edge.target, {
        label: edge.edge_type,
        size: Math.max(edge.weight * 2, 1),
        color: "#65727a"
      });
    }
    if (graph.order > 0 && graph.size > 0) {
      louvain.assign(graph, { nodeCommunityAttribute: "community" });
      const maxDegree = Math.max(...graph.nodes().map((node) => graph.degree(node)), 1);
      graph.forEachNode((node) => {
        const centrality = graph.degree(node) / maxDegree;
        const community = Number(graph.getNodeAttribute(node, "community") ?? 0);
        graph.mergeNodeAttributes(node, {
          size: 4 + centrality * 10,
          color: colorFor(community)
        });
      });
    }
    const renderer = new Sigma(graph, containerRef.current, {
      allowInvalidContainer: true,
      defaultEdgeColor: "#65727a",
      defaultNodeColor: "#2bd4a7",
      labelColor: { color: "#f5f0e8" },
      labelDensity: 0.08,
      labelRenderedSizeThreshold: 9,
      renderEdgeLabels: false
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
  }, [nodes, edges]);

  return (
    <section className="sideSection" aria-label="People graph">
      <div className="sectionHeader">
        <h2>Graph</h2>
        <span>{nodes.length}/{edges.length}</span>
      </div>
      <div className="graphCanvas" ref={containerRef}>
        {nodes.length === 0 ? (
          <p className="emptyInline">
            <Network size={14} /> Run the M3 graph job.
          </p>
        ) : null}
      </div>
    </section>
  );
}

function colorFor(community: number): string {
  return COMMUNITY_COLORS[Math.abs(community) % COMMUNITY_COLORS.length];
}
