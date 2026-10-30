import type { ApiError as ApiErrorBody, ErrorCode as ServerErrorCode } from "../types/api";

/** Server codes plus the ones only the client can produce. */
export type ErrorCode = ServerErrorCode | "NETWORK" | "OFFLINE" | "ABORTED" | "UNKNOWN";

export interface AppError {
  code: ErrorCode;
  message: string;
  retryable: boolean;
  retryAfterMs?: number | null;
  details?: Record<string, unknown>;
  errorId?: string | null;
}

export class ApiRequestError extends Error implements AppError {
  readonly code: ErrorCode;
  readonly retryable: boolean;
  readonly retryAfterMs: number | null;
  readonly details: Record<string, unknown>;
  readonly errorId: string | null;
  readonly status: number;

  constructor(err: AppError, status = 0) {
    super(err.message);
    this.name = "ApiRequestError";
    this.code = err.code;
    this.retryable = err.retryable;
    this.retryAfterMs = err.retryAfterMs ?? null;
    this.details = err.details ?? {};
    this.errorId = err.errorId ?? null;
    this.status = status;
  }

  toJSON(): AppError {
    return {
      code: this.code,
      message: this.message,
      retryable: this.retryable,
      retryAfterMs: this.retryAfterMs,
      details: this.details,
      errorId: this.errorId,
    };
  }
}

export function fromBody(body: ApiErrorBody): AppError {
  return {
    code: body.code,
    message: body.message,
    retryable: body.retryable,
    retryAfterMs: body.retryAfterMs,
    details: body.details,
    errorId: body.errorId,
  };
}

export function toAppError(e: unknown): AppError {
  if (e instanceof ApiRequestError) return e.toJSON();
  if (e instanceof DOMException && e.name === "AbortError") {
    return { code: "ABORTED", message: "Cancelled.", retryable: true };
  }
  return { code: "UNKNOWN", message: "Unexpected error.", retryable: true, errorId: shortId() };
}

export function shortId(): string {
  return Math.random().toString(36).slice(2, 10);
}
