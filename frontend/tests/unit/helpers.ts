import { useGraph } from "../../src/graph/store";
import type { GraphEdge, GraphNode } from "../../src/graph/types";
import type { ImageInputData } from "../../src/nodes/image-input/types";

export function img(id: string, over: Partial<ImageInputData> = {}): GraphNode {
  const data: ImageInputData = {
    fileName: `${id}.jpg`,
    assetId: `ast_${id}`,
    sha256: `sha_${id}`,
    upload: { status: "done", progress: 1, error: null },
    ...over,
  };
  return { id, type: "image-input", version: 1, position: { x: 0, y: 0 }, config: {}, data };
}

export function fusion(id = "f", data: Record<string, unknown> = {}): GraphNode {
  return { id, type: "fusion", version: 1, position: { x: 300, y: 0 }, config: {}, data: { activeRunId: null, runIds: [], ...data } };
}

export function result(id = "r", data: Record<string, unknown> = {}): GraphNode {
  return { id, type: "result", version: 1, position: { x: 600, y: 0 }, config: {}, data: { versions: [], selected: 0, ...data } };
}

export function edge(source: string, target: string, targetPort: string, sourcePort = "out"): GraphEdge {
  return { id: `e-${source}-${target}-${targetPort}`, source, sourcePort, target, targetPort };
}

export function seed(nodes: GraphNode[], edges: GraphEdge[] = []): void {
  useGraph.getState().load({ schemaVersion: 1, graphId: "g-test", nodes, edges });
}
