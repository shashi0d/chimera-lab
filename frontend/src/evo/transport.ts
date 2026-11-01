import type { AppError } from "../api/errors";
import type { AgentEvent, Creature, GalleryPage, Health, Limits, RunSnapshot, StartInput, StartResult } from "./types";

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

/** Everything the UI needs from the agent API (docs/api_contract.md). Real: http.ts. Dev/test: mock.ts. */
export interface EvoTransport {
  readonly kind: "http" | "mock";
  health(): Promise<Health>;
  startRun(input: StartInput): Promise<StartResult>;
  getRun(runId: string): Promise<RunSnapshot>;
  /** Replays every stored event with an id larger than `after`, then streams live until a terminal event. */
  streamEvents(runId: string, after: number, handlers: StreamHandlers): EventStream;
  postChoice(runId: string, choiceId: string, answer: string): Promise<void>;
  getLimits(): Promise<Limits>;
  getCreature(creatureId: string): Promise<Creature>;
  getGallery(cursor?: string | null, limit?: number): Promise<GalleryPage>;
  /** An image URL from the API, as the browser should load it. */
  imageUrl(url: string): string;
}
