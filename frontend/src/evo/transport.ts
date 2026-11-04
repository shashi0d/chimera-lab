import type { AppError } from "../api/errors";
import type { AgentEvent, Health, Limits, RunSnapshot, StartInput, StartResult } from "./types";

export type StreamState = "connecting" | "open" | "reconnecting" | "closed";

export interface StreamHandlers {
  /** Called once per event, in id order, never twice for the same id. */
  onEvent(e: AgentEvent): void;
  onState?(s: StreamState): void;
  /** A failure that ends the stream (e.g. RUN_NOT_FOUND). Transient failures reconnect instead. */
  onError?(err: AppError): void;
}

export interface EventStream {
  stop(): void;
}

/** Everything the UI needs from the Fusion API. The app uses http.ts; tests pass a fake. */
export interface EvoTransport {
  readonly kind: "http" | "fake";
  health(): Promise<Health>;
  startRun(input: StartInput): Promise<StartResult>;
  getRun(runId: string): Promise<RunSnapshot>;
  /** Replays every stored event with an id larger than `after`, then streams live until a terminal event. */
  streamEvents(runId: string, after: number, handlers: StreamHandlers): EventStream;
  getLimits(): Promise<Limits>;
  /** An image URL from the API, as the browser should load it. */
  imageUrl(url: string): string;
}
