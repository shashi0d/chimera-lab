import { create } from "zustand";
import { toAppError, type AppError } from "../api/errors";
import { evo } from "./index";
import type { EventStream, StreamState } from "./transport";
import type {
  AgentEvent,
  CapReachedEvent,
  ErrorEvent,
  FinalizeEvent,
  InspectEvent,
  Mode,
  NeedsChoiceEvent,
  Parent,
  RenderEvent,
  RunAccepted,
  RunSnapshot,
  RunStatus,
  StartedEvent,
  StepEvent,
} from "./types";

/** One agent run as the client knows it: the snapshot plus every event received so far. */
export interface RunRecord {
  runId: string;
  snapshot: RunSnapshot | null;
  /** From the POST response, until a snapshot arrives. */
  accepted: RunAccepted | null;
  events: AgentEvent[];
  stream: StreamState | "idle";
  loadError: AppError | null;
  choice: { sending: boolean; error: AppError | null; sent: string | null };
}

/** A tool call: its step event plus the render / inspect events that share its n. */
export interface TraceStep {
  key: string;
  step: StepEvent | null;
  n: number;
  renders: RenderEvent[];
  inspect: InspectEvent | null;
  at: string;
}

export type TraceItem =
  | { kind: "step"; key: string; data: TraceStep }
  | { kind: "queued"; key: string; position: number; ahead: number; at: string }
  | { kind: "started"; key: string; event: StartedEvent }
  | { kind: "choice"; key: string; event: NeedsChoiceEvent; answer: string | null; by: "user" | "timeout" | null }
  | { kind: "cap"; key: string; event: CapReachedEvent }
  | { kind: "finalize"; key: string; event: FinalizeEvent }
  | { kind: "error"; key: string; event: ErrorEvent };

export interface DerivedRun {
  runId: string;
  status: RunStatus | "loading";
  position: number | null;
  ahead: number | null;
  sire: Parent | null;
  dam: Parent | null;
  mode: Mode | null;
  caps: StartedEvent["caps"] | null;
  startedAt: string | null;
  endedAt: string | null;
  rendersUsed: number;
  toolCalls: number;
  items: TraceItem[];
  images: RenderEvent[];
  verdicts: Record<string, InspectEvent>;
  pendingChoice: NeedsChoiceEvent | null;
  capNotice: CapReachedEvent | null;
  finalize: FinalizeEvent | null;
  error: { code: string; message: string; retryable: boolean } | null;
  lastEventId: number;
}

const TERMINAL: ReadonlySet<string> = new Set(["succeeded", "failed", "interrupted"]);
export function isTerminal(status: DerivedRun["status"]): boolean {
  return TERMINAL.has(status);
}

/** Pure: everything the trace, the Fusion node and the Result node show, from the record. */
export function deriveRun(r: RunRecord): DerivedRun {
  const snap = r.snapshot;
  const items: TraceItem[] = [];
  const steps = new Map<number, TraceStep>();
  const images: RenderEvent[] = [];
  const verdicts: Record<string, InspectEvent> = {};
  const choices = new Map<string, Extract<TraceItem, { kind: "choice" }>>();
  let status: DerivedRun["status"] = snap?.status ?? (r.accepted ? r.accepted.status : "loading");
  let position = snap?.position ?? r.accepted?.position ?? null;
  let ahead: number | null = null;
  let sire = snap?.sire ?? r.accepted?.sire ?? null;
  let dam = snap?.dam ?? r.accepted?.dam ?? null;
  let mode = snap?.mode ?? r.accepted?.mode ?? null;
  let caps: DerivedRun["caps"] = null;
  let startedAt: string | null = null;
  let endedAt: string | null = null;
  let rendersUsed = 0;
  let toolCalls = 0;
  let capNotice: CapReachedEvent | null = null;
  let finalize: FinalizeEvent | null = null;
  let error: DerivedRun["error"] = snap?.error ?? null;
  const open = new Set<string>();

  const stepFor = (n: number, at: string): TraceStep => {
    let s = steps.get(n);
    if (!s) {
      s = { key: `n${n}`, step: null, n, renders: [], inspect: null, at };
      steps.set(n, s);
      items.push({ kind: "step", key: s.key, data: s });
    }
    return s;
  };

  for (const e of r.events) {
    switch (e.type) {
      case "queued":
        status = "queued";
        position = e.position;
        ahead = e.ahead;
        items.push({ kind: "queued", key: `e${e.id}`, position: e.position, ahead: e.ahead, at: e.at });
        break;
      case "started":
        status = "running";
        position = null;
        ahead = null;
        sire = e.sire;
        dam = e.dam;
        mode = e.mode;
        caps = e.caps;
        startedAt = e.at;
        items.push({ kind: "started", key: `e${e.id}`, event: e });
        break;
      case "step": {
        toolCalls += 1;
        // ask_user arrives after its answer and repeats the choice's n: keep it as its own row.
        const s = steps.get(e.n)?.step ? stepFor(e.n + 0.5, e.at) : stepFor(e.n, e.at);
        s.step = e;
        s.at = e.at;
        break;
      }
      case "render":
        stepFor(e.n, e.at).renders.push(e);
        images.push(e);
        if (typeof e.rendersUsed === "number") rendersUsed = Math.max(rendersUsed, e.rendersUsed);
        break;
      case "inspect":
        stepFor(e.n, e.at).inspect = e;
        verdicts[e.imageId] = e;
        break;
      case "needs_choice": {
        open.add(e.choiceId);
        const item = { kind: "choice" as const, key: `c${e.choiceId}`, event: e, answer: null, by: null };
        choices.set(e.choiceId, item);
        items.push(item);
        break;
      }
      case "choice_resolved": {
        open.delete(e.choiceId);
        const c = choices.get(e.choiceId);
        if (c) {
          c.answer = e.answer;
          c.by = e.by;
        }
        break;
      }
      case "cap_reached":
        capNotice = e;
        items.push({ kind: "cap", key: `e${e.id}`, event: e });
        break;
      case "finalize":
        finalize = e;
        status = "succeeded";
        endedAt = e.at;
        items.push({ kind: "finalize", key: `e${e.id}`, event: e });
        break;
      case "error":
        error = { code: e.code, message: e.message, retryable: e.retryable };
        status = "failed";
        endedAt = e.at;
        items.push({ kind: "error", key: `e${e.id}`, event: e });
        break;
    }
  }
  if (status === "needs_choice" && !open.size && r.events.length && !TERMINAL.has(status)) status = "running";
  if (open.size && (status === "running" || status === "queued")) status = "needs_choice";
  // A finished snapshot wins over a partial event list (e.g. the stream has not replayed yet).
  if (snap && TERMINAL.has(snap.status) && !TERMINAL.has(status)) status = snap.status;
  const pending = [...choices.values()].find((c) => open.has(c.event.choiceId))?.event ?? null;
  return {
    runId: r.runId,
    status,
    position,
    ahead,
    sire,
    dam,
    mode,
    caps,
    startedAt: startedAt ?? (snap ? snap.createdAt : null),
    endedAt,
    rendersUsed,
    toolCalls,
    items,
    images,
    verdicts,
    pendingChoice: pending,
    capNotice,
    finalize,
    error,
    lastEventId: r.events[r.events.length - 1]?.id ?? 0,
  };
}

// ------------------------------------------------------------------ local trace cache

const CACHE_PREFIX = "chimera.trace.";
const CACHE_INDEX = "chimera.trace.index";
const CACHE_MAX_RUNS = 12;

export function readCache(runId: string): AgentEvent[] {
  try {
    const raw = JSON.parse(localStorage.getItem(CACHE_PREFIX + runId) ?? "[]") as AgentEvent[];
    // Keep only a gap-free prefix 1..n, so ?after= never skips an event.
    const out: AgentEvent[] = [];
    for (const e of raw) {
      if (e && e.id === out.length + 1) out.push(e);
      else break;
    }
    return out;
  } catch {
    return [];
  }
}

function writeCache(runId: string, events: AgentEvent[]): void {
  try {
    localStorage.setItem(CACHE_PREFIX + runId, JSON.stringify(events));
    const index = (JSON.parse(localStorage.getItem(CACHE_INDEX) ?? "[]") as string[]).filter((id) => id !== runId);
    index.push(runId);
    while (index.length > CACHE_MAX_RUNS) localStorage.removeItem(CACHE_PREFIX + index.shift()!);
    localStorage.setItem(CACHE_INDEX, JSON.stringify(index));
  } catch {
    /* quota or blocked storage: the server replays from ?after=0 instead */
  }
}

// ------------------------------------------------------------------ store

interface RunsState {
  runs: Record<string, RunRecord>;
  attach(runId: string, accepted?: RunAccepted | null): void;
  answerChoice(runId: string, choiceId: string, answer: string): Promise<boolean>;
  /** Test hook: put a record in place without a stream. */
  put(record: RunRecord): void;
}

const streams = new Map<string, EventStream>();
type Listener = (run: DerivedRun) => void;
const listeners = new Set<Listener>();

/** Called with the derived run after every change (the node registry routes it to node types). */
export function onRunChange(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function emptyRecord(runId: string, accepted: RunAccepted | null): RunRecord {
  return { runId, snapshot: null, accepted, events: [], stream: "idle", loadError: null, choice: { sending: false, error: null, sent: null } };
}

export const useEvoRuns = create<RunsState>()((set, get) => {
  const patch = (runId: string, p: Partial<RunRecord> | ((r: RunRecord) => Partial<RunRecord>)) => {
    set((s) => {
      const prev = s.runs[runId] ?? emptyRecord(runId, null);
      return { runs: { ...s.runs, [runId]: { ...prev, ...(typeof p === "function" ? p(prev) : p) } } };
    });
    const rec = get().runs[runId];
    if (rec) {
      const d = deriveRun(rec);
      listeners.forEach((fn) => fn(d));
    }
  };

  const openStream = (runId: string) => {
    if (streams.has(runId)) return;
    const after = get().runs[runId]?.events.length ?? 0;
    const stream = evo().streamEvents(runId, after, {
      onEvent: (e) =>
        patch(runId, (r) => {
          const last = r.events[r.events.length - 1]?.id ?? 0;
          if (e.id <= last) return {};
          const events = [...r.events, e];
          writeCache(runId, events);
          return { events };
        }),
      onState: (st) => {
        patch(runId, { stream: st });
        if (st === "closed") streams.delete(runId);
      },
      onError: (err) => patch(runId, { loadError: err }),
    });
    streams.set(runId, stream);
  };

  return {
    runs: {},

    attach(runId, accepted = null) {
      const existing = get().runs[runId];
      if (existing && (streams.has(runId) || existing.stream === "closed")) {
        if (accepted && !existing.accepted) patch(runId, { accepted });
        return;
      }
      const cached = existing?.events.length ? existing.events : readCache(runId);
      patch(runId, (r) => ({ ...emptyRecord(runId, accepted ?? r.accepted), events: cached, stream: "connecting" }));
      void evo()
        .getRun(runId)
        .then((snapshot) => {
          patch(runId, { snapshot });
          const have = get().runs[runId]?.events.length ?? 0;
          if (TERMINAL.has(snapshot.status) && snapshot.lastEventId > 0 && have >= snapshot.lastEventId) {
            patch(runId, { stream: "closed" }); // finished and fully cached: nothing to stream
            return;
          }
          openStream(runId);
        })
        .catch((e) => {
          const err = toAppError(e);
          if (err.code === "NETWORK") openStream(runId); // the stream reconnects on its own
          else patch(runId, { loadError: err, stream: "closed" });
        });
    },

    async answerChoice(runId, choiceId, answer) {
      patch(runId, { choice: { sending: true, error: null, sent: null } });
      try {
        await evo().postChoice(runId, choiceId, answer);
        patch(runId, { choice: { sending: false, error: null, sent: answer } });
        return true;
      } catch (e) {
        patch(runId, { choice: { sending: false, error: toAppError(e), sent: null } });
        return false;
      }
    },

    put(record) {
      patch(record.runId, record);
    },
  };
});

export function stopAllStreams(): void {
  streams.forEach((s) => s.stop());
  streams.clear();
}

/** Derived view of one run (memoised per record object). */
const memo = new WeakMap<RunRecord, DerivedRun>();
export function derived(r: RunRecord | undefined): DerivedRun | null {
  if (!r) return null;
  let d = memo.get(r);
  if (!d) {
    d = deriveRun(r);
    memo.set(r, d);
  }
  return d;
}

export function useRun(runId: string | null | undefined): DerivedRun | null {
  const rec = useEvoRuns((s) => (runId ? s.runs[runId] : undefined));
  return derived(rec);
}

export function useRunRecord(runId: string | null | undefined): RunRecord | undefined {
  return useEvoRuns((s) => (runId ? s.runs[runId] : undefined));
}
