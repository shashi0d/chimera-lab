import { presentError } from "../api/errorMessages";
import { uuid } from "../api/session";
import { copy } from "../copy";
import { useGraph } from "../graph/store";
import type { GraphEdge, GraphNode, Position } from "../graph/types";
import { prepareImage } from "../nodes/image-input/codec";
import type { ImageInputData } from "../nodes/image-input/types";
import { startUpload } from "../nodes/image-input/uploads";
import { createNode } from "../nodes/registry";
import { putBlob, rememberBlobUrl } from "../persistence/blobStore";
import { toast } from "../ui/toastStore";

export const MAX_IMAGES_PER_DROP = 2;
export const LAYOUT = { imageGapY: 330, fusionDx: 320, resultDx: 380 };

/** Approximate footprints, used only to avoid dropping new nodes on top of old ones. */
export const FOOTPRINT: Record<string, { w: number; h: number }> = {
  "image-input": { w: 240, h: 300 },
  fusion: { w: 300, h: 440 },
  result: { w: 500, h: 660 },
  "field-card": { w: 340, h: 620 },
};
const DEFAULT_FOOTPRINT = { w: 280, h: 300 };

function overlaps(a: Position, aw: number, ah: number, b: Position, bw: number, bh: number): boolean {
  const pad = 24;
  return a.x < b.x + bw + pad && a.x + aw + pad > b.x && a.y < b.y + bh + pad && a.y + ah + pad > b.y;
}

/** Nearest spot at or below/right of `at` where a block of the given size fits. */
export function findFreeSpot(at: Position, w: number, h: number): Position {
  const nodes = useGraph.getState().nodes;
  const hits = (p: Position) =>
    nodes.some((n) => {
      const f = FOOTPRINT[n.type] ?? DEFAULT_FOOTPRINT;
      return overlaps(p, w, h, n.position, f.w, f.h);
    });
  for (let ring = 0; ring < 12; ring++) {
    for (const [dx, dy] of [[1, 0], [0, 1], [1, 1]] as const) {
      const p = { x: at.x + dx * ring * 160, y: at.y + dy * ring * 160 };
      if (!hits(p)) return p;
    }
  }
  return at;
}

function sanitizeName(name: string): string {
  return name.replace(/[^\w.\- ]+/g, "").slice(0, 60) || "image";
}

/**
 * The Fusion node new images should feed: the selected one if it has a free
 * input, otherwise the only Fusion node with free inputs. Null if ambiguous.
 */
function fusionWithFreeSlots(): { node: GraphNode; free: string[] } | null {
  const g = useGraph.getState();
  const candidates = g.nodes
    .filter((n) => n.type === "fusion")
    .map((node) => ({ node, free: ["a", "b"].filter((p) => !g.edges.some((e) => e.target === node.id && e.targetPort === p)) }))
    .filter((c) => c.free.length > 0);
  const selected = candidates.find((c) => g.selection.includes(c.node.id));
  if (selected) return selected;
  return candidates.length === 1 ? candidates[0]! : null;
}

/**
 * Entry point for drop, paste and the file picker (TASKSHEET 7.1).
 * Validates and prepares each file client-side, creates one node per good file,
 * stores the local copy, and starts the upload. On a canvas with no Fusion node,
 * it also adds one and connects the new images to it; with a Fusion node that has
 * free inputs, the new images are wired into it (DECISIONS D-012, D-024).
 */
export async function addImageFiles(files: File[], at: Position): Promise<string[]> {
  const graph = useGraph.getState();
  if (graph.readOnly) return [];
  if (files.length > MAX_IMAGES_PER_DROP) toast.info(copy.input.ignoredExtra(files.length - MAX_IMAGES_PER_DROP));
  const chosen = files.slice(0, MAX_IMAGES_PER_DROP);

  const prepared: Array<{ file: File; blob: Blob; width: number | null; height: number | null }> = [];
  for (const file of chosen) {
    const res = await prepareImage(file);
    if (!res.ok) {
      const p = presentError(res.error);
      toast.error(`${sanitizeName(file.name)}: ${p.title}${p.fix ? ` ${p.fix}` : ""}`);
      continue;
    }
    prepared.push({ file, ...res.image });
  }
  if (!prepared.length) return [];

  const g = useGraph.getState();
  const target = fusionWithFreeSlots();
  const hasFusion = g.nodes.some((n) => n.type === "fusion");
  if (target) {
    // Sit the new images to the left of the Fusion node they feed.
    at = { x: target.node.position.x - LAYOUT.fusionDx, y: target.node.position.y - 20 };
  }
  const blockW = hasFusion ? FOOTPRINT["image-input"]!.w : LAYOUT.fusionDx + FOOTPRINT.fusion!.w;
  const blockH = (prepared.length - 1) * LAYOUT.imageGapY + FOOTPRINT["image-input"]!.h;
  at = findFreeSpot(at, blockW, blockH);
  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];
  for (const [i, p] of prepared.entries()) {
    const blobKey = `img-${uuid()}`;
    await putBlob(blobKey, p.blob);
    rememberBlobUrl(blobKey, p.blob);
    const data: ImageInputData = {
      fileName: sanitizeName(p.file.name),
      blobKey,
      width: p.width ?? undefined,
      height: p.height ?? undefined,
      upload: { status: "queued", progress: 0, error: null },
    };
    nodes.push(createNode("image-input", { x: at.x, y: at.y + i * LAYOUT.imageGapY }, data));
  }

  const connect = (fusionId: string, ports: string[]) =>
    nodes
      .slice(0, ports.length)
      .forEach((img, i) => edges.push({ id: `e-${uuid().slice(0, 8)}`, source: img.id, sourcePort: "out", target: fusionId, targetPort: ports[i]! }));

  if (target) {
    connect(target.node.id, target.free);
    toast.info(target.free.length - Math.min(nodes.length, target.free.length) === 0 ? copy.graph.autoConnectedBoth : copy.graph.autoConnected);
  } else if (!hasFusion) {
    const midY = at.y + ((nodes.length - 1) * LAYOUT.imageGapY) / 2 + (nodes.length === 1 ? 60 : 0);
    const fusion = createNode("fusion", { x: at.x + LAYOUT.fusionDx, y: midY - 40 });
    connect(fusion.id, ["a", "b"]);
    nodes.push(fusion);
    toast.info(edges.length === 2 ? copy.graph.autoConnectedBoth : copy.graph.autoConnected);
  }
  useGraph.getState().addNodes(nodes, edges);
  const ids = nodes.filter((n) => n.type === "image-input").map((n) => n.id);
  ids.forEach((id) => void startUpload(id));
  return ids;
}

/** Replace the image on an existing node: keeps id and edges, marks results downstream stale. */
export async function replaceImage(nodeId: string, file: File): Promise<void> {
  const res = await prepareImage(file);
  if (!res.ok) {
    const p = presentError(res.error);
    toast.error(`${sanitizeName(file.name)}: ${p.title}${p.fix ? ` ${p.fix}` : ""}`);
    return;
  }
  const blobKey = `img-${uuid()}`;
  await putBlob(blobKey, res.image.blob);
  rememberBlobUrl(blobKey, res.image.blob);
  const g = useGraph.getState();
  g.checkpoint();
  g.updateNodeData<ImageInputData>(nodeId, () => ({
    fileName: sanitizeName(file.name),
    blobKey,
    width: res.image.width ?? undefined,
    height: res.image.height ?? undefined,
    upload: { status: "queued", progress: 0, error: null },
    flagged: null,
  }));
  g.markDownstreamStale(nodeId);
  await startUpload(nodeId);
}
