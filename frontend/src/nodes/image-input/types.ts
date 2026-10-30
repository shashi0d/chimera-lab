import type { AppError } from "../../api/errors";

export type UploadStatus = "processing" | "queued" | "uploading" | "done" | "error" | "cancelled";

export interface ImageInputData extends Record<string, unknown> {
  fileName: string;
  /** IndexedDB key of the local copy (preview + offline queue). */
  blobKey?: string;
  assetId?: string;
  sha256?: string;
  width?: number;
  height?: number;
  serverUrl?: string;
  upload: { status: UploadStatus; progress: number; error?: AppError | null };
  /** Set when a fusion failed because of this input. */
  flagged?: string | null;
}

export type ImageInputConfig = Record<string, never>;
