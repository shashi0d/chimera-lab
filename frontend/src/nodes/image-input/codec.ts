import type { AppError } from "../../api/errors";
import { fileError, MAX_UPLOAD_BYTES, MIN_SHORT_SIDE, precheck, targetSize } from "./validate";

export interface PreparedImage {
  blob: Blob;
  width: number | null;
  height: number | null;
}

export type PrepareResult = { ok: true; image: PreparedImage } | { ok: false; error: AppError };

export interface ImageCodec {
  /** Decode with EXIF orientation applied. Throws if undecodable. */
  decode(file: Blob): Promise<{ width: number; height: number; source: CanvasImageSource; close(): void }>;
  /** Re-encode at the given size. Re-encoding drops all metadata (GPS included). */
  encode(source: CanvasImageSource, width: number, height: number, type: "image/jpeg" | "image/png"): Promise<Blob>;
}

export const browserCodec: ImageCodec = {
  async decode(file) {
    const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
    return { width: bmp.width, height: bmp.height, source: bmp, close: () => bmp.close() };
  },
  async encode(source, width, height, type) {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("no 2d context");
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(source, 0, 0, width, height);
    return new Promise((resolve, reject) => canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("encode failed"))), type, 0.92));
  },
};

let codec: ImageCodec = browserCodec;
export function setImageCodec(c: ImageCodec): void {
  codec = c;
}

/**
 * Client-side pipeline (TASKSHEET 7.1): size, real type, decode, min size,
 * EXIF orientation, downscale to 2048px, metadata stripped by re-encoding.
 * R1: the agent API takes JPEG, PNG or WebP only, so HEIC is converted here when the browser can
 * decode it (Safari) and refused as UNSUPPORTED_FILE when it can't. A PNG that would exceed the
 * API's 8 MB limit is re-encoded as JPEG.
 */
export async function prepareImage(file: Blob): Promise<PrepareResult> {
  const pre = await precheck(file);
  if ("error" in pre) return { ok: false, error: pre.error };
  let decoded: Awaited<ReturnType<ImageCodec["decode"]>>;
  try {
    decoded = await codec.decode(file);
  } catch {
    return { ok: false, error: fileError(pre.kind === "heif" ? "UNSUPPORTED_FILE" : "IMAGE_CORRUPT") };
  }
  try {
    if (Math.min(decoded.width, decoded.height) < MIN_SHORT_SIDE) {
      return { ok: false, error: fileError("IMAGE_TOO_SMALL", { width: decoded.width, height: decoded.height }) };
    }
    const size = targetSize(decoded.width, decoded.height);
    const type = pre.kind === "png" ? "image/png" : "image/jpeg";
    let blob = await codec.encode(decoded.source, size.width, size.height, type);
    if (type === "image/png" && blob.size > MAX_UPLOAD_BYTES) blob = await codec.encode(decoded.source, size.width, size.height, "image/jpeg");
    return { ok: true, image: { blob, width: size.width, height: size.height } };
  } catch {
    return { ok: false, error: fileError("IMAGE_CORRUPT") };
  } finally {
    decoded.close();
  }
}
