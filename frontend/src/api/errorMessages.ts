import type { AppError, ErrorCode } from "./errors";

export interface ErrorPresentation {
  title: string;
  /** What to change, or what happens next. */
  fix?: string;
  /** Show a retry button. */
  retry: boolean;
}

/**
 * One user-facing message per error code. Raw server/upstream text is never shown: the R1 refusal and cap
 * wording follows written here so it can be edited in one place.
 */
export const errorMessages: Record<ErrorCode, ErrorPresentation> = {
  VALIDATION_FAILED: { title: "Something in the request wasn't valid.", fix: "Check both animals and try again.", retry: false },
  UNSUPPORTED_FILE: { title: "That file type isn't supported.", fix: "Use a JPEG, PNG or WebP image.", retry: false },
  FILE_TOO_LARGE: { title: "That image is too large.", fix: "Images must be 8 MB or smaller.", retry: false },
  IMAGE_CORRUPT: { title: "That image is damaged and can't be read.", fix: "Try a different copy of the photo.", retry: false },
  IMAGE_TOO_SMALL: { title: "That image is too small.", fix: "Use a photo at least 256 px on its short side.", retry: false },
  NOT_AN_ANIMAL: { title: "We couldn't find an animal in this image.", fix: "Replace the highlighted photo, or type the animal's name instead.", retry: false },
  HUMAN_DETECTED: { title: "This looks like a photo of a person.", fix: "Chimera Lab only uses animal photos. Use a photo with only the animal in it.", retry: false },
  DUPLICATE_INPUTS: { title: "Both inputs are the same image.", fix: "Use two different animals.", retry: false },
  GRAPH_INVALID: { title: "The Fusion node isn't wired up correctly.", fix: "Give each slot, A and B, a photo or a name.", retry: false },
  RATE_LIMITED: { title: "Too many runs were started from here just now.", retry: true },
  UPSTREAM_TIMEOUT: { title: "The model took too long to answer, so this run ended.", fix: "Nothing was charged to you. Try again in a few minutes.", retry: true },
  UPSTREAM_ERROR: { title: "The image model stopped answering, so this run ended.", fix: "Nothing was charged to you. Try again in a few minutes.", retry: true },
  MODEL_REFUSED: { title: "The image model declined this pair.", fix: "Try a different photo of either animal.", retry: false },
  BUDGET_EXCEEDED: { title: "This run reached its budget and stopped.", fix: "Start a new creature, or come back tomorrow.", retry: false },
  CAP_REACHED: { title: "Today's Fusion runs are used up.", fix: "New runs open again tomorrow.", retry: false },
  RUN_NOT_FOUND: { title: "This run can't be found.", fix: "It may have expired. Start a new creature instead.", retry: false },
  RUN_INTERRUPTED: { title: "The server restarted while this creature was being made.", fix: "Nothing was charged to you. Start it again.", retry: true },
  NOT_FOUND: { title: "That item no longer exists.", retry: false },
  INTERNAL: { title: "Something went wrong on our side.", retry: true },
  NETWORK: { title: "Couldn't reach the server.", retry: true },
  OFFLINE: { title: "You're offline.", fix: "Reconnect to continue.", retry: false },
  ABORTED: { title: "Cancelled.", retry: true },
  UNKNOWN: { title: "Something unexpected happened.", retry: true },
};

/** "00:00 UTC" from an ISO time. */
function utc(iso: unknown): string | null {
  if (typeof iso !== "string" || Number.isNaN(Date.parse(iso))) return null;
  const d = new Date(iso);
  return `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")} UTC`;
}

export function presentError(err: AppError): ErrorPresentation & { errorId?: string } {
  let p = errorMessages[err.code] ?? errorMessages.UNKNOWN;
  const at = err.code === "CAP_REACHED" ? utc((err.details as { resetsAt?: unknown } | undefined)?.resetsAt) : null;
  if (at) p = { ...p, fix: `New runs open again at ${at}.` };
  const errorId = err.code === "INTERNAL" || err.code === "UNKNOWN" ? err.errorId ?? undefined : undefined;
  return { ...p, retry: p.retry && err.retryable !== false, errorId };
}
