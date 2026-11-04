// Test-only fake of the Fusion API. The app is live-only and never imports this; component and unit tests install it
// with setTransport(). A run replays a short event list (queued?, started, step, render, finalize or error) on a
// compressed clock, so following a run, resuming and the error path work without a backend.
import { ApiRequestError, type AppError } from "../../src/api/errors";
import type { EventStream, EvoTransport, StreamHandlers } from "../../src/evo/transport";
import type { AgentEvent, Limits, Parent, RunAccepted, RunSnapshot, RunStatus, StartInput, StartResult } from "../../src/evo/types";

export const MOCK_SCENARIOS = [
  "success",
  "queued",
  "error",
  "identify_choice",
  "refused_human",
  "refused_type",
  "refused_size",
  "refused_animal",
  "refused_corrupt",
  "cap_daily",
  "limits_capped",
  "rate_limited",
] as const;
export type MockScenario = (typeof MOCK_SCENARIOS)[number];

export const mockConfig = {
  scenario: "success" as MockScenario,
  /** Time between replayed events. */
  stepMs: 200,
  /** Hold the replay at this event id. Null replays to the end. */
  holdAt: null as number | null,
  latencyMs: 20,
};

export const RESETS_AT = "2026-11-03T00:00:00Z";
export const RUN_ERROR_MESSAGE = "The image model stopped answering, so this run ended.";

const REFUSALS: Partial<Record<MockScenario, { code: string; status: number; message: string }>> = {
  refused_human: { code: "HUMAN_DETECTED", status: 422, message: "This photo shows a person. Use a photo of an animal." },
  refused_animal: { code: "NOT_AN_ANIMAL", status: 422, message: "No animal was found in this photo." },
  refused_type: { code: "UNSUPPORTED_FILE", status: 415, message: "Use a JPEG, PNG or WebP image." },
  refused_size: { code: "FILE_TOO_LARGE", status: 413, message: "This image is too large." },
  refused_corrupt: { code: "IMAGE_CORRUPT", status: 422, message: "This image is damaged and can't be read." },
};

const parent = (commonName: string, source: Parent["source"]): Parent => ({ commonName, scientificName: null, source, confidence: source === "image" ? 0.94 : null });

interface MockRun {
  runId: string;
  startedAt: number;
  accepted: RunAccepted;
  events: AgentEvent[];
}
const runs = new Map<string, MockRun>();
let dailyCapHit = false;

/** The events a run of this kind emits, in order (ids from 1). Exported for tests that put a run in place. */
export function runEvents(kind: "success" | "queued" | "error", runId: string, sire: Parent, dam: Parent): AgentEvent[] {
  const at = (i: number) => new Date(Date.UTC(2026, 10, 3, 12, 0, i)).toISOString();
  const out: Array<Omit<AgentEvent, "id" | "runId" | "at">> = [];
  if (kind === "queued") out.push({ type: "queued", position: 2, ahead: 2 } as Omit<AgentEvent, "id" | "runId" | "at">);
  out.push({ type: "started", sire, dam, style: "real" } as Omit<AgentEvent, "id" | "runId" | "at">);
  out.push({ type: "step", n: 1, tool: "render", summary: "rendered", ok: true } as Omit<AgentEvent, "id" | "runId" | "at">);
  if (kind === "error") {
    out.push({ type: "error", code: "UPSTREAM_TIMEOUT", message: RUN_ERROR_MESSAGE, retryable: true } as Omit<AgentEvent, "id" | "runId" | "at">);
  } else {
    out.push({ type: "render", n: 1, imageId: "img1", url: `/evo/files/runs/${runId}/img1.png` } as Omit<AgentEvent, "id" | "runId" | "at">);
    out.push({ type: "finalize", creatureId: `crt_${runId}`, imageId: "img1", imageUrl: `/evo/files/runs/${runId}/img1.png` } as Omit<AgentEvent, "id" | "runId" | "at">);
  }
  return out.map((e, i) => ({ ...e, id: i + 1, runId, at: at(i) }) as AgentEvent);
}

function released(run: MockRun, now = Date.now()): AgentEvent[] {
  const n = Math.floor((now - run.startedAt) / mockConfig.stepMs) + 1;
  const upTo = mockConfig.holdAt ?? Infinity;
  return run.events.slice(0, Math.max(0, n)).filter((e) => e.id <= upTo);
}

function statusOf(run: MockRun, events: AgentEvent[]): { status: RunStatus; position: number | null } {
  const last = events[events.length - 1];
  if (!last) return { status: run.accepted.status, position: run.accepted.position };
  if (last.type === "finalize") return { status: "succeeded", position: null };
  if (last.type === "error") return { status: "failed", position: null };
  if (last.type === "queued") return { status: "queued", position: last.position };
  return { status: "running", position: null };
}

function fail(code: string, status: number, message: string, details: Record<string, unknown> = {}, retryAfterMs?: number): never {
  throw new ApiRequestError({ code: code as AppError["code"], message, retryable: status === 429 && code === "RATE_LIMITED", details, ...(retryAfterMs ? { retryAfterMs } : {}) }, status);
}

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

function startRun(kind: "success" | "queued" | "error", label: string, sire: Parent, dam: Parent): RunAccepted {
  const runId = `run_fx_${label}-${Math.random().toString(36).slice(2, 10)}`;
  const accepted: RunAccepted = {
    runId,
    status: kind === "queued" ? "queued" : "running",
    position: kind === "queued" ? 2 : null,
    eventsUrl: `/evo/agent/runs/${runId}/events`,
    runUrl: `/evo/agent/runs/${runId}`,
    sire,
    dam,
    style: "real",
  };
  runs.set(runId, { runId, startedAt: Date.now(), accepted, events: runEvents(kind, runId, sire, dam) });
  return accepted;
}

export const mockTransport: EvoTransport = {
  kind: "fake",

  async health() {
    await wait(mockConfig.latencyMs);
    return { status: "ok" };
  },

  async startRun(input: StartInput): Promise<StartResult> {
    await wait(mockConfig.latencyMs);
    const s = mockConfig.scenario;
    if (s === "cap_daily" || s === "limits_capped" || dailyCapHit) {
      dailyCapHit = s === "cap_daily" || dailyCapHit;
      fail("CAP_REACHED", 429, "You've used today's Fusion runs. New runs open again at 00:00 UTC.", { scope: "visitor_daily", limit: 3, resetsAt: RESETS_AT });
    }
    if (s === "rate_limited") fail("RATE_LIMITED", 429, "You're starting runs too quickly. Wait a minute and try again.", {}, 3000);
    const refusal = REFUSALS[s];
    if (refusal) fail(refusal.code, refusal.status, refusal.message, { slot: "sire" });
    if (s === "identify_choice") {
      if (input.sireImage && !input.sireName) {
        return {
          kind: "identify",
          status: "needs_choice",
          choice: {
            kind: "identify",
            slot: "sire",
            question: "Which animal is in photo A?",
            options: [
              { commonName: "Galápagos tortoise", scientificName: "Chelonoidis niger", confidence: 0.48 },
              { commonName: "Aldabra giant tortoise", scientificName: "Aldabrachelys gigantea", confidence: 0.31 },
            ],
            allowOther: true,
          },
          identified: { sire: null, dam: parent("domestic goat", "image") },
        };
      }
      return { kind: "accepted", ...startRun("success", "identify", parent(input.sireName ?? "animal", "name"), parent(input.damName ?? "animal", "name")) };
    }
    const sire = input.sireImage ? parent("Indian pangolin", "image") : parent(input.sireName ?? "animal", input.sireVersionId ? "version" : "name");
    const dam = input.damImage ? parent("horse", "image") : parent(input.damName ?? "animal", input.damVersionId ? "version" : "name");
    const kind = s === "queued" ? "queued" : s === "error" ? "error" : "success";
    return { kind: "accepted", ...startRun(kind, s, sire, dam) };
  },

  async getRun(runId): Promise<RunSnapshot> {
    await wait(mockConfig.latencyMs);
    const run = runs.get(runId);
    if (!run) fail("RUN_NOT_FOUND", 404, "This run doesn't exist.");
    const events = released(run);
    const { status, position } = statusOf(run, events);
    const last = events[events.length - 1];
    const fin = events.find((e) => e.type === "finalize");
    const err = events.find((e) => e.type === "error");
    return {
      runId,
      status,
      position,
      sire: run.accepted.sire,
      dam: run.accepted.dam,
      style: "real",
      createdAt: new Date(run.startedAt).toISOString(),
      updatedAt: last?.at ?? new Date().toISOString(),
      lastEventId: last?.id ?? 0,
      creatureId: fin?.type === "finalize" ? fin.creatureId : null,
      error: err?.type === "error" ? { code: err.code, message: err.message, retryable: err.retryable } : null,
    };
  },

  streamEvents(runId, after, h: StreamHandlers): EventStream {
    let stopped = false;
    let last = after;
    h.onState?.("connecting");
    const timer = setInterval(tick, 50);
    function tick() {
      if (stopped) return;
      const run = runs.get(runId);
      if (!run) {
        stop();
        h.onError?.({ code: "RUN_NOT_FOUND", message: "This run doesn't exist.", retryable: false });
        h.onState?.("closed");
        return;
      }
      for (const e of released(run)) {
        if (e.id <= last) continue;
        last = e.id;
        h.onEvent(e);
        if (e.type === "finalize" || e.type === "error") {
          stop();
          h.onState?.("closed");
          return;
        }
      }
    }
    function stop() {
      stopped = true;
      clearInterval(timer);
    }
    setTimeout(() => {
      if (!stopped) h.onState?.("open");
      tick();
    }, mockConfig.latencyMs);
    return { stop };
  },

  async getLimits(): Promise<Limits> {
    await wait(mockConfig.latencyMs);
    const capped = mockConfig.scenario === "limits_capped" || dailyCapHit;
    return {
      liveRuns: capped ? "capped" : "open",
      dailyTotal: { used: capped ? 50 : 4, limit: 50, resetsAt: RESETS_AT },
      visitor: { used: capped ? 3 : 1, limit: 3 },
      concurrent: { running: 0, limit: 3, queued: 0 },
    };
  },

  imageUrl(url) {
    return url;
  },
};

/** Test hook: forget mock runs and the daily-cap latch. */
export function resetMock(): void {
  dailyCapHit = false;
  runs.clear();
  mockConfig.scenario = "success";
  mockConfig.holdAt = null;
}
