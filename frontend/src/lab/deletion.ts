import { toAppError } from "../api/errors";
import { presentError } from "../api/errorMessages";
import { useGraph } from "../graph/store";
import type { GraphNode } from "../graph/types";
import type { ImageInputData } from "../nodes/image-input/types";
import type { VersionData } from "../nodes/version/types";
import { deleteBlob } from "../persistence/blobStore";
import { confirmAction } from "../ui/ConfirmDialog";
import { toast } from "../ui/toastStore";
import { labApi } from "./api";

/**
 * Deleting an image is permanent: a generated image is removed from the server (its record and files), a photo's
 * copy is removed from this device. A confirmation comes first; other cards (Fusion, edits) are removed without one.
 * After an image is deleted, undo history is cleared so undo cannot bring back a card whose image is gone.
 */

function imagesIn(nodes: GraphNode[]): { versions: string[]; photos: string[] } {
  const versions: string[] = [];
  const photos: string[] = [];
  for (const n of nodes) {
    if (n.type === "version") {
      const id = (n.data as VersionData).version?.id;
      if (id) versions.push(id);
    } else if (n.type === "image-input") {
      const key = (n.data as ImageInputData).blobKey;
      if (key) photos.push(key);
    }
  }
  return { versions, photos };
}

let clearHistory = false;

/** Ask before deleting nodes that hold images; delete those images if confirmed. True: go ahead with the delete. */
export async function confirmImageDelete(nodeIds: string[]): Promise<boolean> {
  const nodes = useGraph.getState().nodes.filter((n) => nodeIds.includes(n.id));
  const { versions, photos } = imagesIn(nodes);
  const count = versions.length + photos.length;
  if (!count) return true;
  const ok = await confirmAction({
    title: count === 1 ? "Delete this image?" : `Delete ${count} images?`,
    body:
      (versions.length ? "Generated images are removed from your library and the server, with their animal cards. " : "") +
      (photos.length ? "Photos are removed from this device. " : "") +
      "This can't be undone.",
    confirmLabel: count === 1 ? "Delete image" : "Delete images",
    danger: true,
  });
  if (!ok) return false;
  const failed: string[] = [];
  await Promise.all([
    ...versions.map((id) =>
      labApi.deleteVersion(id).catch((e) => {
        const err = toAppError(e);
        if (err.code !== "NOT_FOUND") failed.push(presentError(err).title);
      }),
    ),
    ...photos.map((key) => deleteBlob(key).catch(() => undefined)),
  ]);
  if (failed.length) toast.error(`Some images could not be deleted from the server: ${failed[0]}`);
  clearHistory = true;
  return true;
}

/** Called after the canvas removed the nodes: forget undo steps that could restore a deleted image. */
export function afterNodesDeleted(): void {
  if (!clearHistory) return;
  clearHistory = false;
  useGraph.setState({ past: [], future: [] });
}

/** Delete from a card's own button: confirm, then remove the nodes. */
export async function deleteNodes(nodeIds: string[]): Promise<void> {
  if (!(await confirmImageDelete(nodeIds))) return;
  useGraph.getState().removeNodes(nodeIds);
  afterNodesDeleted();
}
