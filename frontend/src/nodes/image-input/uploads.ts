import { api } from "../../api/client";
import { toAppError } from "../../api/errors";
import { onceOnline, useConnectivity } from "../../connectivity/store";
import { useGraph } from "../../graph/store";
import { getBlob } from "../../persistence/blobStore";
import type { ImageInputData } from "./types";

const active = new Map<string, () => void>();

function patch(nodeId: string, p: Partial<ImageInputData> | ((d: ImageInputData) => Partial<ImageInputData>)): void {
  useGraph.getState().updateNodeData<ImageInputData>(nodeId, (d) => ({ ...d, ...(typeof p === "function" ? p(d) : p) }));
}

function nodeData(nodeId: string): ImageInputData | undefined {
  return useGraph.getState().nodes.find((n) => n.id === nodeId)?.data as ImageInputData | undefined;
}

export function isUploading(nodeId: string): boolean {
  return active.has(nodeId);
}

/** Upload the node's local blob. Offline: mark queued; the queue flushes on reconnect. */
export async function startUpload(nodeId: string): Promise<void> {
  const data = nodeData(nodeId);
  if (!data?.blobKey || active.has(nodeId)) return;
  if (useConnectivity.getState().status !== "online") {
    patch(nodeId, { upload: { status: "queued", progress: 0, error: null } });
    return;
  }
  const blob = await getBlob(data.blobKey);
  if (!blob) {
    patch(nodeId, { upload: { status: "error", progress: 0, error: { code: "IMAGE_CORRUPT", message: "Local copy missing.", retryable: false } } });
    return;
  }
  patch(nodeId, { upload: { status: "uploading", progress: 0, error: null } });
  const { promise, abort } = api.uploadAsset(blob, data.fileName || "image.jpg", (fraction) => {
    patch(nodeId, (d) => ({ upload: { ...d.upload, progress: Math.min(0.99, fraction) } }));
  });
  active.set(nodeId, abort);
  try {
    const asset = await promise;
    patch(nodeId, {
      assetId: asset.assetId,
      sha256: asset.sha256,
      width: asset.width,
      height: asset.height,
      serverUrl: asset.url,
      upload: { status: "done", progress: 1, error: null },
    });
  } catch (e) {
    const err = toAppError(e);
    if (err.code === "ABORTED") patch(nodeId, { upload: { status: "cancelled", progress: 0, error: null } });
    else if (err.code === "NETWORK") patch(nodeId, { upload: { status: "queued", progress: 0, error: null } });
    else patch(nodeId, { upload: { status: "error", progress: 0, error: err } });
  } finally {
    active.delete(nodeId);
  }
}

export function cancelUpload(nodeId: string): void {
  active.get(nodeId)?.();
}

export function queuedNodeIds(): string[] {
  return useGraph
    .getState()
    .nodes.filter((n) => n.type === "image-input" && (n.data as ImageInputData).upload?.status === "queued")
    .map((n) => n.id);
}

export function flushUploadQueue(): void {
  for (const id of queuedNodeIds()) void startUpload(id);
}

/** Start queued uploads whenever we come back online. */
export function startUploadQueue(): () => void {
  let stop = () => undefined as void;
  const arm = () => {
    stop = onceOnline(() => {
      flushUploadQueue();
      // re-arm for the next offline/online cycle
      queueMicrotask(() => {
        stop();
        armAfterDrop();
      });
    });
  };
  const armAfterDrop = () => {
    const unsub = useConnectivity.subscribe((s, prev) => {
      if (s.status !== "online" && prev.status === "online") {
        unsub();
        arm();
      }
    });
    stop = unsub;
  };
  arm();
  return () => stop();
}
