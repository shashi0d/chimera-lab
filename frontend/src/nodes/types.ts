import type { FC } from "react";
import type { ConnectivityStatus } from "../connectivity/store";
import type { GraphDoc, GraphNode, NodeConfig, NodeData, PortSpec } from "../graph/types";
import type { IconName } from "../ui/Icon";

export interface ValidationIssue {
  code: string;
  message: string;
  /** "block" disables the node's Run button; "warn" is advisory. */
  severity: "block" | "warn";
  /** Node the issue points at (for highlighting), if not the node itself. */
  nodeId?: string;
}

export interface ValidationContext {
  graph: Pick<GraphDoc, "nodes" | "edges">;
  connectivity: ConnectivityStatus;
  readOnly: boolean;
}

export interface NodeViewProps<C = NodeConfig, D = NodeData> {
  node: GraphNode<C, D>;
  selected: boolean;
  issues: ValidationIssue[];
  /** Stable catalog number shown on the card ("No.03"). */
  catalog: number;
}

export interface NodePanelProps<C = NodeConfig, D = NodeData> {
  node: GraphNode<C, D>;
  onClose: () => void;
}

/** One node type, defined once (TASKSHEET 4.1). */
export interface NodeDefinition<C = NodeConfig, D = NodeData> {
  type: string;
  /** Bump when the config/data shape changes, and add `migrate`. */
  version: number;
  label: string;
  category: "input" | "process" | "output";
  icon: IconName;
  /** Shown as an "Add …" button on the tool rail. */
  addable: boolean;
  inputs: PortSpec[];
  outputs: PortSpec[];
  defaultConfig: C;
  defaultData(): D;
  validate(node: GraphNode<C, D>, ctx: ValidationContext): ValidationIssue[];
  View: FC<NodeViewProps<C, D>>;
  Panel?: FC<NodePanelProps<C, D>>;
  /** Shows a Run/Fuse button. */
  runnable: boolean;
  migrate?(oldConfig: unknown, oldData: unknown, fromVersion: number): { config: C; data: D };
}

/** The registry stores definitions with their generics erased. */
export type AnyNodeDefinition = NodeDefinition<NodeConfig, NodeData>;

export function defineNode<C extends NodeConfig, D extends NodeData>(def: NodeDefinition<C, D>): AnyNodeDefinition {
  return def as unknown as AnyNodeDefinition;
}
