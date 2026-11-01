import type { AppError } from "../../api/errors";

/** R1: images stay on this device until a run starts; they go up with POST /evo/agent/runs and are never stored there. */
export type ImageStatus = "processing" | "ready" | "error";

export interface ImageInputData extends Record<string, unknown> {
  fileName: string;
  /** IndexedDB key of the prepared local copy (preview, and the bytes sent when a run starts). */
  blobKey?: string;
  /** SHA-256 of the prepared copy: the same photo in both slots is refused before anything is sent. */
  sha256?: string;
  width?: number;
  height?: number;
  status: ImageStatus;
  error?: AppError | null;
  /** The animal the agent API identified in this photo (latest run). */
  species?: string | null;
  /** Set when a run was refused because of this photo. */
  flagged?: string | null;
}

export type ImageInputConfig = Record<string, never>;

/** v1 data had an upload state and a server asset; v2 keeps only the local copy. */
export function migrateImageData(old: unknown): ImageInputData {
  const d = (old ?? {}) as Record<string, unknown> & { upload?: { status?: string } };
  const ok = typeof d.blobKey === "string";
  return {
    fileName: typeof d.fileName === "string" ? d.fileName : "",
    blobKey: ok ? (d.blobKey as string) : undefined,
    sha256: typeof d.sha256 === "string" ? d.sha256 : undefined,
    width: typeof d.width === "number" ? d.width : undefined,
    height: typeof d.height === "number" ? d.height : undefined,
    status: ok ? "ready" : "error",
    error: ok ? null : { code: "IMAGE_CORRUPT", message: "Local copy missing.", retryable: false },
    species: null,
    flagged: null,
  };
}
