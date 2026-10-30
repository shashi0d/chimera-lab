import type { GraphDoc, GraphEdge, GraphNode } from "./types";

export function nodeById(graph: Pick<GraphDoc, "nodes">, id: string): GraphNode | undefined {
  return graph.nodes.find((n) => n.id === id);
}

export function edgeInto(graph: Pick<GraphDoc, "edges">, nodeId: string, port: string): GraphEdge | undefined {
  return graph.edges.find((e) => e.target === nodeId && e.targetPort === port);
}

export function upstreamNode(graph: Pick<GraphDoc, "nodes" | "edges">, nodeId: string, port: string): GraphNode | undefined {
  const edge = edgeInto(graph, nodeId, port);
  return edge ? nodeById(graph, edge.source) : undefined;
}

export function downstreamIds(graph: Pick<GraphDoc, "edges">, nodeId: string): string[] {
  const out = new Set<string>();
  const stack = [nodeId];
  while (stack.length) {
    const id = stack.pop() as string;
    for (const e of graph.edges) {
      if (e.source === id && !out.has(e.target)) {
        out.add(e.target);
        stack.push(e.target);
      }
    }
  }
  return [...out];
}

export function wouldCreateCycle(graph: Pick<GraphDoc, "edges">, source: string, target: string): boolean {
  if (source === target) return true;
  return downstreamIds(graph, target).includes(source);
}
