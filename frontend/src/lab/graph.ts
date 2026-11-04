import { findFreeSpot, FOOTPRINT } from "../canvas/addImages";
import { upstreamNode } from "../graph/queries";
import { useGraph } from "../graph/store";
import type { GraphNode } from "../graph/types";
import { createNode } from "../nodes/registry";
import type { EditConfig, EditData, EditOperation } from "../nodes/edit/types";
import type { VersionData } from "../nodes/version/types";
import type { CardData } from "../nodes/card/types";
import type { FusionData } from "../nodes/fusion/types";
import type { LabVersion } from "./api";

/**
 * The Lab's one flow on the canvas (FLORA-style): Fusion → image (V1) → edit card → image (V2) → … Every image is
 * a `version` node; every change is an `edit` node between two images, so the path from the animals to the final
 * creature stays on the canvas.
 */

const GAP = 90;

function rightOf(node: GraphNode, type: string): { x: number; y: number } {
  const w = FOOTPRINT[node.type]?.w ?? 300;
  const size = FOOTPRINT[type] ?? { w: 300, h: 360 };
  return findFreeSpot({ x: node.position.x + w + GAP, y: node.position.y }, size.w, size.h);
}

export function versionNodes(): GraphNode<Record<string, unknown>, VersionData>[] {
  return useGraph.getState().nodes.filter((n) => n.type === "version") as GraphNode<Record<string, unknown>, VersionData>[];
}

export function findVersionNode(versionId: string): GraphNode | undefined {
  return versionNodes().find((n) => n.data.version?.id === versionId);
}

/** The Fusion run's version-1 card (pending until the run finishes). */
export function findRunVersionNode(runId: string): GraphNode | undefined {
  return versionNodes().find((n) => n.data.runId === runId || (n.data.version?.operation === "fusion" && n.data.version.runId === runId));
}

/** A card for the image that `source` (a Fusion or edit node) produced, to its right and connected. */
export function addVersionNode(sourceId: string, data: VersionData): string {
  const g = useGraph.getState();
  const source = g.nodes.find((n) => n.id === sourceId);
  const node = createNode("version", source ? rightOf(source, "version") : { x: 0, y: 0 }, data);
  g.addNodes([node], source ? [{ id: `e-${node.id}`, source: sourceId, sourcePort: "out", target: node.id, targetPort: "in" }] : []);
  return node.id;
}

/** A new edit card after an image (Revise or Paint), selected and ready for the instruction. */
export function addEditNode(versionNodeId: string, operation: EditOperation, instruction = "", at?: { x: number; y: number }): string {
  const g = useGraph.getState();
  const parent = g.nodes.find((n) => n.id === versionNodeId);
  const size = FOOTPRINT.edit!;
  const position = at ? findFreeSpot(at, size.w, size.h) : parent ? rightOf(parent, "edit") : { x: 0, y: 0 };
  const node = createNode("edit", position);
  node.config = { operation, instruction } satisfies EditConfig;
  g.addNodes([node], [{ id: `e-${node.id}`, source: versionNodeId, sourcePort: "out", target: node.id, targetPort: "in" }]);
  g.setSelection([node.id]);
  requestAnimationFrame(() => document.querySelector<HTMLTextAreaElement>(`[data-node-id="${CSS.escape(node.id)}"] textarea`)?.focus());
  return node.id;
}

/** An animal card for an image (written as soon as the image is ready). */
export function addCardNode(versionNodeId: string, at?: { x: number; y: number }): string {
  const g = useGraph.getState();
  const parent = g.nodes.find((n) => n.id === versionNodeId);
  const size = FOOTPRINT.card!;
  const position = at ? findFreeSpot(at, size.w, size.h) : parent ? rightOf(parent, "card") : { x: 0, y: 0 };
  const node = createNode("card", position, { card: null, versionId: null, autoStart: true, error: null } satisfies CardData);
  g.addNodes([node], [{ id: `e-${node.id}`, source: versionNodeId, sourcePort: "out", target: node.id, targetPort: "in" }]);
  g.setSelection([node.id]);
  return node.id;
}

/** A new Fusion with this image as animal A: type or connect animal B to make a creature from it. */
export function addFusionFrom(versionNodeId: string, at?: { x: number; y: number }): string {
  const g = useGraph.getState();
  const parent = g.nodes.find((n) => n.id === versionNodeId);
  const size = FOOTPRINT.fusion!;
  const position = at ? findFreeSpot(at, size.w, size.h) : parent ? rightOf(parent, "fusion") : { x: 0, y: 0 };
  const node = createNode("fusion", position, { activeRunId: null, runIds: [], names: { a: "", b: "" } } satisfies FusionData);
  g.addNodes([node], [{ id: `e-${node.id}`, source: versionNodeId, sourcePort: "out", target: node.id, targetPort: "a" }]);
  g.setSelection([node.id]);
  return node.id;
}

/** The image an edit card changes (its connected input). */
export function parentVersionOf(editNodeId: string): { node: GraphNode; version: LabVersion | null } | null {
  const up = upstreamNode(useGraph.getState(), editNodeId, "in");
  return up && up.type === "version" ? { node: up, version: (up.data as VersionData).version } : null;
}

/** Version cards from the first image (V1) to this one, following the canvas edges back through edit cards. */
export function lineage(versionNodeId: string): GraphNode[] {
  const g = useGraph.getState();
  const out: GraphNode[] = [];
  const seen = new Set<string>();
  let current = g.nodes.find((n) => n.id === versionNodeId);
  while (current && !seen.has(current.id)) {
    seen.add(current.id);
    if (current.type === "version") out.unshift(current);
    const up = upstreamNode(g, current.id, "in");
    current = up && (up.type === "version" || up.type === "edit") ? up : undefined;
  }
  return out;
}

/** "V3": the card's place in its path (V1 is the Fusion image). */
export function versionNumber(versionNodeId: string): number {
  return lineage(versionNodeId).length;
}

/** All version cards that share this card's first image (its creature's tree), in creation order. */
export function treeOf(versionNodeId: string): GraphNode[] {
  const root = lineage(versionNodeId)[0]?.id;
  return versionNodes().filter((n) => lineage(n.id)[0]?.id === root);
}

export function editNodesWithJobs(): GraphNode<EditConfig, EditData>[] {
  return useGraph.getState().nodes.filter((n) => n.type === "edit") as unknown as GraphNode<EditConfig, EditData>[];
}
