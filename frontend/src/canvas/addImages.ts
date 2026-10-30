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
export const LAYOUT = { imageGapY: 300, fusionDx: 320, resultDx: 360 };

function sanitizeName(name: string): string {
  return name.replace(/[^\w.\- ]+/g, "").slice(0, 60) || "image";
}

/**
 * Entry point for drop, paste and the file picker (TASKSHEET 7.1).
 * Validates and prepares each file client-side, creates one node per good file,
 * stores the local copy, and starts the upload. On a canvas with no Fusion node,
 * it also adds one and connects the new images to it (DECISIONS D-012).
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

  const hasFusion = useGraph.getState().nodes.some((n) => n.type === "fusion");
  if (!hasFusion) {
    const midY = at.y + ((nodes.length - 1) * LAYOUT.imageGapY) / 2 + (nodes.length === 1 ? 60 : 0);
    const fusion = createNode("fusion", { x: at.x + LAYOUT.fusionDx, y: midY - 40 });
    nodes.push(fusion);
    nodes
      .filter((n) => n.type === "image-input")
      .forEach((img, i) => edges.push({ id: `e-${uuid().slice(0, 8)}`, source: img.id, sourcePort: "out", target: fusion.id, targetPort: i === 0 ? "a" : "b" }));
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
