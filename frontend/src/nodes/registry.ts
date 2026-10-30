// Node registry (TASKSHEET 4.1). Adding a node type = a folder under nodes/ plus one line here.
import { uuid } from "../api/session";
import type { GraphNode, NodeData, Position } from "../graph/types";
import { fieldCardNode } from "./field-card/definition";
import { fusionNode } from "./fusion/definition";
import { imageInputNode } from "./image-input/definition";
import { resultNode } from "./result/definition";
import { onRunUpdate } from "../runs/store";
import { useGraph } from "../graph/store";
import type { AnyNodeDefinition } from "./types";

const definitions: AnyNodeDefinition[] = [imageInputNode, fusionNode, resultNode, fieldCardNode];

export const nodeRegistry: Readonly<Record<string, AnyNodeDefinition>> = Object.freeze(
  Object.fromEntries(definitions.map((d) => [d.type, d])),
);

export function getDefinition(type: string): AnyNodeDefinition | undefined {
  return nodeRegistry[type];
}

export function portsOf(type: string) {
  const def = nodeRegistry[type];
  return def ? { inputs: def.inputs, outputs: def.outputs } : undefined;
}

export function createNode(type: string, position: Position, data?: NodeData): GraphNode {
  const def = nodeRegistry[type];
  if (!def) throw new Error(`Unknown node type ${type}`);
  return {
    id: `${type}-${uuid().slice(0, 8)}`,
    type,
    version: def.version,
    position,
    config: { ...def.defaultConfig },
    data: { ...def.defaultData(), ...data },
  };
}

/** Routes every run update to its node type's `onRunUpdate` (no per-type wiring in the app shell). */
export function registerRunHandlers(): () => void {
  return onRunUpdate((nodeId, run) => {
    const node = useGraph.getState().nodes.find((n) => n.id === nodeId);
    if (node) nodeRegistry[node.type]?.onRunUpdate?.(nodeId, run);
  });
}
