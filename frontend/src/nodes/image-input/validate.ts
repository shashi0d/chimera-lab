import type { AppError } from "../../api/errors";
import { errorMessages } from "../../api/errorMessages";

export const MAX_BYTES = 20 * 1024 * 1024;
export const MIN_SHORT_SIDE = 256;
export const MAX_EDGE = 2048;
export const ACCEPT_ATTR = "image/jpeg,image/png,image/webp,image/heic,image/heif,.heic,.heif";

export type ImageKind = "jpeg" | "png" | "webp" | "heif";

/** Sniff the real format from magic bytes; extensions and MIME types are not trusted. */
export function sniffKind(head: Uint8Array): ImageKind | null {
  const at = (i: number) => head[i] ?? -1;
  const ascii = (from: number, to: number) => String.fromCharCode(...Array.from(head.slice(from, to)));
  if (at(0) === 0xff && at(1) === 0xd8 && at(2) === 0xff) return "jpeg";
  if (at(0) === 0x89 && ascii(1, 4) === "PNG") return "png";
  if (ascii(0, 4) === "RIFF" && ascii(8, 12) === "WEBP") return "webp";
  if (ascii(4, 8) === "ftyp" && ["heic", "heix", "hevc", "hevx", "mif1", "msf1", "heif"].includes(ascii(8, 12))) return "heif";
  return null;
}

export function fileError(code: "UNSUPPORTED_FILE" | "FILE_TOO_LARGE" | "IMAGE_CORRUPT" | "IMAGE_TOO_SMALL", details?: Record<string, unknown>): AppError {
  return { code, message: errorMessages[code].title, retryable: false, details };
}

/** Cheap checks that need no decoding. */
export async function precheck(file: Blob): Promise<{ kind: ImageKind } | { error: AppError }> {
  if (file.size > MAX_BYTES) return { error: fileError("FILE_TOO_LARGE", { size: file.size }) };
  const head = new Uint8Array(await file.slice(0, 16).arrayBuffer());
  const kind = sniffKind(head);
  if (!kind) return { error: fileError("UNSUPPORTED_FILE") };
  return { kind };
}

export function targetSize(width: number, height: number): { width: number; height: number; scaled: boolean } {
  const long = Math.max(width, height);
  if (long <= MAX_EDGE) return { width, height, scaled: false };
  const k = MAX_EDGE / long;
  return { width: Math.round(width * k), height: Math.round(height * k), scaled: true };
}
