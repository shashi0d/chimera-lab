// Client side of docs/api_contract.md (R1 agent API). Field names follow the contract exactly.
// The UI reads only these derived camelCase fields; it never parses the engine's `card` or `plan`.

export type Mode = "realistic" | "speculative" | "mythic";
export const MODES: readonly Mode[] = ["realistic", "speculative", "mythic"];

export interface Parent {
  commonName: string;
  scientificName: string | null;
  source: "image" | "name";
  confidence: number | null;
}

export type Slot = "sire" | "dam";

export type RunStatus = "queued" | "running" | "needs_choice" | "succeeded" | "failed" | "interrupted";

/** 202 from POST /evo/agent/runs. */
export interface RunAccepted {
  runId: string;
  status: "queued" | "running";
  position: number | null;
  eventsUrl: string;
  runUrl: string;
  sire: Parent;
  dam: Parent;
  mode: Mode;
}

export interface IdentifyOption {
  commonName: string;
  scientificName: string | null;
  confidence: number | null;
}

/** 200 from POST /evo/agent/runs: identification was not confident; no run was created. */
export interface IdentifyChoice {
  status: "needs_choice";
  choice: { kind: "identify"; slot: Slot; question: string; options: IdentifyOption[]; allowOther: boolean };
  identified: { sire: Parent | null; dam: Parent | null };
}

export type StartResult = ({ kind: "accepted" } & RunAccepted) | ({ kind: "identify" } & IdentifyChoice);

export interface StartInput {
  mode: Mode;
  sireImage?: Blob | null;
  damImage?: Blob | null;
  sireName?: string | null;
  damName?: string | null;
}

export interface PendingChoice {
  choiceId: string;
  kind: "host_tie";
  question: string;
  options: string[];
  expiresAt: string;
}

/** GET /evo/agent/runs/{runId}. */
export interface RunSnapshot {
  runId: string;
  status: RunStatus;
  position: number | null;
  sire: Parent;
  dam: Parent;
  mode: Mode;
  createdAt: string;
  updatedAt: string;
  lastEventId: number;
  creatureId: string | null;
  error: { code: string; message: string; retryable: boolean } | null;
  pendingChoice: PendingChoice | null;
}

export interface Failure {
  key: string;
  kind: "structural" | "covering" | string;
  text: string;
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
  mode: Mode;
  caps: { renders: number; toolCalls: number; seconds: number };
}
export interface StepEvent extends EventBase {
  type: "step";
  n: number;
  tool: string;
  args: Record<string, unknown>;
  summary: string;
  reason: string;
  cards: string[];
  ok: boolean;
  error: string | null;
}
export interface RenderEvent extends EventBase {
  type: "render";
  n: number;
  imageId: string;
  url: string;
  kind: "render" | "edit" | "growth_host" | "growth" | string;
  parent: string | null;
  method: string;
  rendersUsed: number | null;
  rendersLeft: number | null;
}
export interface InspectEvent extends EventBase {
  type: "inspect";
  n: number;
  imageId: string;
  verdict: "pass" | "fail" | string;
  failures: Failure[];
  hiddenChecks: number;
  bestSoFar: string | null;
  rule: string | null;
}
export interface NeedsChoiceEvent extends EventBase {
  type: "needs_choice";
  n: number;
  choiceId: string;
  kind: "host_tie";
  question: string;
  options: string[];
  expiresAt: string;
}
export interface ChoiceResolvedEvent extends EventBase {
  type: "choice_resolved";
  choiceId: string;
  answer: string | null;
  by: "user" | "timeout";
}
export interface CapReachedEvent extends EventBase {
  type: "cap_reached";
  scope: "renders" | "tool_calls" | "time";
  limit: number;
  message: string;
}
export interface FinalizeEvent extends EventBase {
  type: "finalize";
  creatureId: string;
  imageId: string;
  imageUrl: string;
  remainingFailures: Failure[];
  hiddenChecks: number;
  agree: boolean;
  stop: string;
}
export interface ErrorEvent extends EventBase {
  type: "error";
  code: string;
  message: string;
  retryable: boolean;
}

export type AgentEvent =
  | QueuedEvent
  | StartedEvent
  | StepEvent
  | RenderEvent
  | InspectEvent
  | NeedsChoiceEvent
  | ChoiceResolvedEvent
  | CapReachedEvent
  | FinalizeEvent
  | ErrorEvent;

export const EVENT_TYPES: ReadonlySet<AgentEvent["type"]> = new Set([
  "queued",
  "started",
  "step",
  "render",
  "inspect",
  "needs_choice",
  "choice_resolved",
  "cap_reached",
  "finalize",
  "error",
]);

export function isTerminalEvent(e: AgentEvent): boolean {
  return e.type === "finalize" || e.type === "error";
}

export interface Limits {
  liveRuns: "open" | "capped";
  dailyTotal: { used: number; limit: number; resetsAt: string };
  visitor: { used: number; limit: number };
  concurrent: { running: number; limit: number; queued: number };
}

export interface Pick {
  imageId: string;
  imageUrl: string;
  rank: number;
  of: number;
  structural: number;
  failures: number;
  reason: string;
}

export interface AnatomyPart {
  part: string;
  parent: string;
  parentRole: "host" | "donor" | "blend";
  status: "found" | "not located" | string;
  color: string | null;
  maskArea: number;
}

export interface Creature {
  creatureId: string;
  createdAt: string;
  title: string;
  sire: Parent;
  dam: Parent;
  mode: Mode;
  generatedLabel: string;
  realHybrid: boolean;
  showcase: boolean;
  imageUrl: string;
  host: { commonName: string; reason: string; tie: boolean; chosenBy: "agent" | "user" | "code" };
  canItLive: {
    summary: string;
    functions: Array<{ function: string; result: "pass" | "fail" | string; detail: string }>;
    licenses: Array<{ rule: string; compensation: string }>;
  };
  remainingFailures: Failure[];
  hiddenChecks: number;
  finalChoice: { shownFirst: "agent"; agree: boolean; agentPick: Pick; codePick: Pick };
  anatomyMap: { overlayUrl: string; colors: { host: string; donor: string; blend: string }; parts: AnatomyPart[] } | null;
  images: Array<{ imageId: string; url: string; kind: string; verdict: "pass" | "fail" | null }>;
  runId: string | null;
  stats: { renders: number; edits: number; toolCalls: number; seconds: number };
}

export interface GalleryItem {
  creatureId: string;
  title: string;
  sire: Parent;
  dam: Parent;
  mode: Mode;
  imageUrl: string;
  showcase: boolean;
  createdAt: string;
}

export interface GalleryPage {
  items: GalleryItem[];
  nextCursor: string | null;
}

export interface Health {
  mode: "mock" | "real" | null;
}
