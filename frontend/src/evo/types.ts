// Client side of the Fusion API (POST /evo/agent/runs, its snapshot and its SSE events, limits, health).

/** The art style a Fusion renders in. */
export type Style = "real" | "drawing" | "anime" | "comic" | "cartoon";
export const STYLES: readonly Style[] = ["real", "drawing", "anime", "comic", "cartoon"];

export interface Parent {
  commonName: string;
  scientificName: string | null;
  source: "image" | "name" | "version";
  confidence: number | null;
  /** Set when the parent is an earlier generated creature (source "version"). */
  versionId?: string;
}

export type Slot = "sire" | "dam";

export type RunStatus = "queued" | "running" | "succeeded" | "failed" | "interrupted";

/** 202 from POST /evo/agent/runs. */
export interface RunAccepted {
  runId: string;
  status: "queued" | "running";
  position: number | null;
  eventsUrl: string;
  runUrl: string;
  sire: Parent;
  dam: Parent;
  style?: Style;
}

export interface IdentifyOption {
  commonName: string;
  scientificName: string | null;
  confidence: number | null;
}

/** 200 from POST /evo/agent/runs: a photo was not identified confidently; no run was created. */
export interface IdentifyChoice {
  status: "needs_choice";
  choice: { kind: "identify"; slot: Slot; question: string; options: IdentifyOption[]; allowOther: boolean };
  identified: { sire: Parent | null; dam: Parent | null };
}

export type StartResult = ({ kind: "accepted" } & RunAccepted) | ({ kind: "identify" } & IdentifyChoice);

export interface StartInput {
  style?: Style;
  /** An earlier generated creature as the parent: its image goes to the image model. */
  sireVersionId?: string | null;
  damVersionId?: string | null;
  /** The workspace the run's images belong to. */
  workspaceId?: string | null;
  sireImage?: Blob | null;
  damImage?: Blob | null;
  sireName?: string | null;
  damName?: string | null;
}

/** GET /evo/agent/runs/{runId}. */
export interface RunSnapshot {
  runId: string;
  status: RunStatus;
  position: number | null;
  sire: Parent;
  dam: Parent;
  style?: Style;
  createdAt: string;
  updatedAt: string;
  lastEventId: number;
  creatureId: string | null;
  error: { code: string; message: string; retryable: boolean } | null;
}

interface EventBase {
  id: number;
  runId: string;
  at: string;
}

export interface QueuedEvent extends EventBase {
  type: "queued";
  position: number;
  ahead: number;
}
export interface StartedEvent extends EventBase {
  type: "started";
  sire: Parent;
  dam: Parent;
  style?: Style;
}
export interface StepEvent extends EventBase {
  type: "step";
  n: number;
  tool: string;
  summary: string;
  ok: boolean;
}
export interface RenderEvent extends EventBase {
  type: "render";
  n: number;
  imageId: string;
  url: string;
}
export interface FinalizeEvent extends EventBase {
  type: "finalize";
  creatureId: string;
  imageId: string;
  imageUrl: string;
  title?: string;
}
export interface ErrorEvent extends EventBase {
  type: "error";
  code: string;
  message: string;
  retryable: boolean;
}

export type AgentEvent = QueuedEvent | StartedEvent | StepEvent | RenderEvent | FinalizeEvent | ErrorEvent;

export const EVENT_TYPES: ReadonlySet<AgentEvent["type"]> = new Set(["queued", "started", "step", "render", "finalize", "error"]);

export function isTerminalEvent(e: AgentEvent): boolean {
  return e.type === "finalize" || e.type === "error";
}

/** The visitor's lifetime images (a Fusion or an edit is 1, an animal card 4). `limit` and `left` are null with no limit. */
export interface ImageQuota {
  used: number;
  limit: number | null;
  left: number | null;
  costs?: { fusion: number; edit: number; card: number };
}

export interface Limits {
  liveRuns: "open" | "capped";
  /** Set when the server has no limits (EVO_LIMITS_ENABLED off): the numbers are counts only. */
  unlimited?: boolean;
  dailyTotal: { used: number; limit: number; resetsAt: string };
  visitor: { used: number; limit: number };
  concurrent: { running: number; limit: number; queued: number };
  images?: ImageQuota;
}

export interface Health {
  status: string;
}
