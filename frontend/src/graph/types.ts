/** Versioned graph document (TASKSHEET 4.2). This is what autosave and the backend store. */

export const CURRENT_SCHEMA_VERSION = 1;

export interface Position {
  x: number;
  y: number;
}

export type NodeConfig = Record<string, unknown>;
export type NodeData = Record<string, unknown>;

export interface GraphNode<C = NodeConfig, D = NodeData> {
  id: string;
  type: string;
  version: number;
  position: Position;
  config: C;
  data: D;
}

export interface GraphEdge {
  id: string;
  source: string;
  sourcePort: string;
  target: string;
  targetPort: string;
}

export interface GraphDoc {
  schemaVersion: number;
  graphId: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export type PortType = "image" | "creature";

export interface PortSpec {
  id: string;
  label?: string;
  /** Input ports: data types it takes. */
  accepts?: PortType[];
  /** Output ports: data type it emits. */
  emits?: PortType;
  /** Input ports: allow more than one connection. */
  many?: boolean;
}
