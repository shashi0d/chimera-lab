import type { AppError, ErrorCode } from "./errors";

export interface ErrorPresentation {
  title: string;
  /** What to change, for non-retryable errors. */
  fix?: string;
  /** Show a retry button. */
  retry: boolean;
}

/** One user-facing message per error code. Raw server/upstream text is never shown. */
export const errorMessages: Record<ErrorCode, ErrorPresentation> = {
  VALIDATION_FAILED: { title: "Something in the request wasn't valid.", fix: "Reload the page and try again.", retry: false },
  UNSUPPORTED_FILE: { title: "That file type isn't supported.", fix: "Use a JPEG, PNG, WebP or HEIC photo.", retry: false },
  FILE_TOO_LARGE: { title: "That file is over 20 MB.", fix: "Export a smaller copy and add it again.", retry: false },
  IMAGE_CORRUPT: { title: "That image is damaged and can't be read.", fix: "Try a different copy of the photo.", retry: false },
  IMAGE_TOO_SMALL: { title: "That image is too small.", fix: "Use a photo at least 256 px on its short side.", retry: false },
  NOT_AN_ANIMAL: { title: "We couldn't find an animal in one of the images.", fix: "Replace the highlighted image with a clear animal photo.", retry: false },
  HUMAN_DETECTED: { title: "One of the images shows a person.", fix: "For privacy, use photos with only the animal in them.", retry: false },
  DUPLICATE_INPUTS: { title: "Both inputs are the same image.", fix: "Connect two different animals.", retry: false },
  GRAPH_INVALID: { title: "The Fusion node isn't wired up correctly.", fix: "Connect one image to each input, A and B.", retry: false },
  RATE_LIMITED: { title: "The models are busy right now.", retry: true },
  UPSTREAM_TIMEOUT: { title: "The model took too long to answer.", retry: true },
  UPSTREAM_ERROR: { title: "The model service had a problem.", retry: true },
  MODEL_REFUSED: { title: "The image model declined this pair.", fix: "Try a different photo of either animal.", retry: false },
  BUDGET_EXCEEDED: { title: "Today's image generation budget is used up.", fix: "Fusions will be available again tomorrow.", retry: false },
  RUN_NOT_FOUND: { title: "This fusion run can't be found anymore.", fix: "Fuse again to start a new run.", retry: false },
  RUN_INTERRUPTED: { title: "The server restarted while this fusion was running.", retry: true },
  NOT_FOUND: { title: "That item no longer exists.", retry: false },
  INTERNAL: { title: "Something went wrong on our side.", retry: true },
  NETWORK: { title: "Couldn't reach the server.", retry: true },
  OFFLINE: { title: "You're offline.", fix: "Reconnect to continue.", retry: false },
  ABORTED: { title: "Cancelled.", retry: true },
  UNKNOWN: { title: "Something unexpected happened.", retry: true },
};

export function presentError(err: AppError): ErrorPresentation & { errorId?: string } {
  const p = errorMessages[err.code] ?? errorMessages.UNKNOWN;
  const errorId = err.code === "INTERNAL" || err.code === "UNKNOWN" ? err.errorId ?? undefined : undefined;
  return { ...p, retry: p.retry && err.retryable !== false, errorId };
}
