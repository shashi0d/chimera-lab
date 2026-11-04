// Test-only, fixture-backed fake of the agent API (docs/api_contract.md, docs/api_fixtures/). The app is live-only
// and never imports this; component and unit tests install it with setTransport().
//
// Runs replay the fixture's events on a compressed clock that survives reloads (localStorage), so
// resume-after-reload, Last-Event-ID replay, the host-tie ask, the queue and the error path all work
// without a backend. The scenario is picked with ?mock=<scenario> or window.__chimera.mock (test mode).
import { ApiRequestError } from "../../src/api/errors";
import type { EventStream, EvoTransport, StreamHandlers } from "../../src/evo/transport";
import type { AgentEvent, Creature, GalleryPage, Limits, RunAccepted, RunSnapshot, RunStatus, StartInput, StartResult } from "../../src/evo/types";

type Json = Record<string, unknown>;
interface Fixture {
  name: string;
  response?: { status: number; body: Json };
  events?: AgentEvent[];
  creature?: Creature;
  cases?: Array<{ response: { status: number; body: Json } }>;
  followUp?: { response: { status: number; body: Json } };
}

const raw = import.meta.glob<Fixture>("../../../docs/api_fixtures/*.json", { eager: true, import: "default" });
const FX: Record<string, Fixture> = Object.fromEntries(Object.entries(raw).map(([path, f]) => [path.split("/").pop()!.replace(".json", ""), f]));
function fx(name: string): Fixture {
  const f = FX[name];
  if (!f) throw new Error(`missing fixture ${name}`);
  return f;
}

export const MOCK_SCENARIOS = [
  "success",
  "host_tie",
  "cap",
  "error",
  "queued",
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

const RUN_FIXTURE: Partial<Record<MockScenario, string>> = {
  success: "run_success",
  host_tie: "run_host_tie",
  cap: "run_cap",
  error: "run_error",
  queued: "run_queued",
};

export const mockConfig = {
  scenario: "success" as MockScenario,
  /** Time between replayed events. */
  stepMs: 700,
  /** Hold the replay at this event id (screenshots of a run mid-way). Null replays to the end. */
  holdAt: null as number | null,
  /** How long a host-tie question waits before the agent decides itself (the contract default is 120 s). */
  choiceMs: 120_000,
  latencyMs: 120,
  /** Base the fixture's relative image paths are served from. */
  imageBase: "/__fixtures/",
};

export function isMockScenario(s: string | null | undefined): s is MockScenario {
  return Boolean(s && (MOCK_SCENARIOS as readonly string[]).includes(s));
}

// ------------------------------------------------------------------ persistent run registry

interface MockRun {
  fixture: string;
  startedAt: number;
  /** choiceId -> when and how it was answered */
  answers: Record<string, { answer: string; at: number }>;
}

const REG_KEY = "chimera.mock.runs";
const memory: Record<string, MockRun> = {};

function registry(): Record<string, MockRun> {
  try {
    return { ...memory, ...(JSON.parse(localStorage.getItem(REG_KEY) ?? "{}") as Record<string, MockRun>) };
  } catch {
    return { ...memory };
  }
}
function saveRun(id: string, run: MockRun): void {
  memory[id] = run;
  try {
    const all = registry();
    all[id] = run;
    const ids = Object.keys(all).slice(-30);
    localStorage.setItem(REG_KEY, JSON.stringify(Object.fromEntries(ids.map((k) => [k, all[k]]))));
  } catch {
    /* storage blocked: memory only */
  }
}

/** Fixture run ids open directly (e.g. ?run=run_fx_success) as finished runs. */
function lookup(runId: string): MockRun | null {
  const r = registry()[runId];
  if (r) return r;
  for (const name of Object.values(RUN_FIXTURE)) {
    const f = fx(name!);
    if ((f.response?.body as { runId?: string } | undefined)?.runId === runId) return { fixture: name!, startedAt: 0, answers: {} };
  }
  return null;
}

let counter = 0;
function newRunId(base: string): string {
  counter += 1;
  return `${base}-${Date.now().toString(36)}${counter}`;
}

// ------------------------------------------------------------------ the replay clock

function img(url: string): string {
  return /^(https?:|blob:|data:|\/)/.test(url) ? url : `${mockConfig.imageBase}${url}`;
}

function remapEvent(e: AgentEvent, runId: string, at: number): AgentEvent {
  const out = { ...e, runId, at: new Date(at).toISOString() } as AgentEvent;
  if (out.type === "render") out.url = img(out.url);
  if (out.type === "finalize") out.imageUrl = img(out.imageUrl);
  if (out.type === "needs_choice") out.expiresAt = new Date(at + mockConfig.choiceMs).toISOString();
  return out;
}

/** The events this run has emitted by `now` (ids stay gap-free, as the contract requires). */
export function releasedEvents(runId: string, run: MockRun, now = Date.now()): AgentEvent[] {
  const events = fx(run.fixture).events ?? [];
  // A fixture run opened by its own id is a finished run: every event, at the fixture's own times.
  if (run.startedAt === 0) return events.map((e) => remapEvent(e, runId, Date.parse(e.at)));
  const out: AgentEvent[] = [];
  let t = run.startedAt;
  let skipResolved: string | null = null;
  for (const e of events) {
    if (mockConfig.holdAt !== null && e.id > mockConfig.holdAt) break;
    if (e.type === "choice_resolved" && skipResolved === e.choiceId) {
      skipResolved = null;
      continue;
    }
    t += mockConfig.stepMs;
    if (t > now) break;
    const prev = out[out.length - 1];
    if (prev?.type === "needs_choice") {
      const answered = run.answers[prev.choiceId];
      const expires = Date.parse(prev.expiresAt);
      if (answered) {
        t = Math.max(t, answered.at);
        if (e.type === "choice_resolved") {
          out.push({ ...remapEvent(e, runId, t), id: out.length + 1, answer: answered.answer, by: "user" } as AgentEvent);
          continue;
        }
      } else if (now >= expires) {
        t = expires;
        out.push({ id: out.length + 1, type: "choice_resolved", runId, at: new Date(t).toISOString(), choiceId: prev.choiceId, answer: null, by: "timeout" });
        if (e.type === "choice_resolved") continue;
        skipResolved = prev.choiceId;
        t += mockConfig.stepMs;
        if (t > now) break;
      } else break;
    }
    out.push({ ...remapEvent(e, runId, t), id: out.length + 1 } as AgentEvent);
  }
  return out;
}

function statusOf(events: AgentEvent[]): { status: RunStatus; position: number | null } {
  let status: RunStatus = "running";
  let position: number | null = null;
  const open = new Set<string>();
  for (const e of events) {
    if (e.type === "queued") {
      status = "queued";
      position = e.position;
    } else if (e.type === "started") {
      status = "running";
      position = null;
    } else if (e.type === "needs_choice") open.add(e.choiceId);
    else if (e.type === "choice_resolved") open.delete(e.choiceId);
    else if (e.type === "finalize") status = "succeeded";
    else if (e.type === "error") status = "failed";
  }
  if (open.size && status === "running") status = "needs_choice";
  return { status, position };
}

// ------------------------------------------------------------------ creatures

function withImages(c: Creature): Creature {
  return {
    ...c,
    imageUrl: img(c.imageUrl),
    images: c.images.map((i) => ({ ...i, url: img(i.url) })),
    finalChoice: {
      ...c.finalChoice,
      agentPick: { ...c.finalChoice.agentPick, imageUrl: img(c.finalChoice.agentPick.imageUrl) },
      codePick: { ...c.finalChoice.codePick, imageUrl: img(c.finalChoice.codePick.imageUrl) },
    },
    anatomyMap: c.anatomyMap ? { ...c.anatomyMap, overlayUrl: img(c.anatomyMap.overlayUrl) } : null,
  };
}

/**
 * No fixture has the agent and the code ranking disagreeing (finalChoice.agree false), so the mock adds one,
 * constructed from b10 and labelled as constructed in its reasons, to exercise the both-picks view.
 */
export const SPLIT_CREATURE_ID = "crt_mock_b10_split";
function splitCreature(): Creature {
  const base = fx("run_host_tie").creature!;
  return {
    ...base,
    creatureId: SPLIT_CREATURE_ID,
    showcase: false,
    imageUrl: "images/b10_img3.jpg",
    finalChoice: {
      shownFirst: "agent",
      agree: false,
      agentPick: {
        imageId: "img3",
        imageUrl: "images/b10_img3.jpg",
        rank: 2,
        of: 4,
        structural: 1,
        failures: 2,
        reason: "Constructed for the UI mock: the agent prefers img3 because the shell pattern reads as one continuous covering.",
      },
      codePick: { ...base.finalChoice.codePick, rank: 1, failures: 2, structural: 1 },
    },
  };
}

function creatures(): Record<string, Creature> {
  const out: Record<string, Creature> = {};
  const b09 = fx("creature_b09").response?.body as unknown as Creature | undefined;
  if (b09) out[b09.creatureId] = b09;
  for (const name of Object.values(RUN_FIXTURE)) {
    const c = fx(name!).creature;
    if (c) out[c.creatureId] = c;
  }
  out[SPLIT_CREATURE_ID] = splitCreature();
  return out;
}

// ------------------------------------------------------------------ helpers

const wait = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
function fail(body: Json, status: number): never {
  const e = (body as { error: { code: string; message: string; retryable: boolean; retryAfterMs?: number; details?: Json } }).error;
  throw new ApiRequestError({ code: e.code as never, message: e.message, retryable: e.retryable, retryAfterMs: e.retryAfterMs ?? null, details: e.details ?? {} }, status);
}

const REFUSAL_CASE: Partial<Record<MockScenario, string>> = {
  refused_human: "HUMAN_DETECTED",
  refused_type: "UNSUPPORTED_FILE",
  refused_size: "FILE_TOO_LARGE",
  refused_animal: "NOT_AN_ANIMAL",
};

let dailyCapHit = false;

function startFixtureRun(name: string, body?: Json): RunAccepted {
  const f = fx(name);
  const res = { ...((body ?? f.response!.body) as unknown as RunAccepted) };
  const runId = newRunId(res.runId);
  saveRun(runId, { fixture: name, startedAt: Date.now(), answers: {} });
  return { ...res, runId, eventsUrl: `/evo/agent/runs/${runId}/events`, runUrl: `/evo/agent/runs/${runId}` };
}

// ------------------------------------------------------------------ the transport

export const mockTransport: EvoTransport = {
  kind: "fake",

  async health() {
    await wait(mockConfig.latencyMs / 2);
    return { status: "ok" };
  },

  async startRun(input: StartInput): Promise<StartResult> {
    await wait(mockConfig.latencyMs * 3);
    const s = mockConfig.scenario;
    if (s === "cap_daily" || s === "limits_capped" || dailyCapHit) {
      dailyCapHit = s === "cap_daily" || dailyCapHit;
      const r = fx("cap_daily").response!;
      fail(r.body, r.status);
    }
    if (s === "rate_limited") {
      fail({ error: { code: "RATE_LIMITED", message: "Too many runs started from here. Try again in a few seconds.", retryable: true, retryAfterMs: 3000, details: {} } }, 429);
    }
    const refusal = REFUSAL_CASE[s];
    if (refusal) {
      const c = fx("upload_refused").cases!.find((x) => (x.response.body as { error: { code: string } }).error.code === refusal)!;
      fail(c.response.body, c.response.status);
    }
    if (s === "refused_corrupt") {
      fail({ error: { code: "IMAGE_CORRUPT", message: "This image is damaged and can't be read.", retryable: false, details: { slot: "sire" } } }, 422);
    }
    if (s === "identify_choice") {
      const f = fx("identify_choice");
      if (input.sireImage && !input.sireName) return { kind: "identify", ...(f.response!.body as unknown as Omit<StartResult & { kind: "identify" }, "kind">) };
      return { kind: "accepted", ...startFixtureRun("run_host_tie", f.followUp!.response.body) };
    }
    return { kind: "accepted", ...startFixtureRun(RUN_FIXTURE[s] ?? "run_success") };
  },

  async getRun(runId): Promise<RunSnapshot> {
    await wait(mockConfig.latencyMs);
    const run = lookup(runId);
    if (!run) fail({ error: { code: "RUN_NOT_FOUND", message: "This run does not exist.", retryable: false, details: {} } }, 404);
    const f = fx(run.fixture);
    const body = f.response!.body as unknown as RunAccepted;
    const events = releasedEvents(runId, run);
    // Before its first event a run is as the POST described it (e.g. queued at position 2).
    const { status, position } = events.length ? statusOf(events) : { status: body.status as RunStatus, position: body.position };
    const fin = events.find((e) => e.type === "finalize");
    const err = events.find((e) => e.type === "error");
    const resolved = new Set(events.filter((e) => e.type === "choice_resolved").map((e) => (e as { choiceId: string }).choiceId));
    const pending = events.find((e) => e.type === "needs_choice" && !resolved.has(e.choiceId));
    const last = events[events.length - 1];
    return {
      runId,
      status,
      position,
      sire: body.sire,
      dam: body.dam,
      mode: body.mode,
      createdAt: new Date(run.startedAt || Date.now()).toISOString(),
      updatedAt: last?.at ?? new Date().toISOString(),
      lastEventId: last?.id ?? 0,
      creatureId: fin?.type === "finalize" ? fin.creatureId : null,
      error: err?.type === "error" ? { code: err.code, message: err.message, retryable: err.retryable } : null,
      pendingChoice:
        pending?.type === "needs_choice"
          ? { choiceId: pending.choiceId, kind: "host_tie", question: pending.question, options: pending.options, expiresAt: pending.expiresAt }
          : null,
    };
  },

  streamEvents(runId, after, h: StreamHandlers): EventStream {
    let stopped = false;
    let last = after;
    h.onState?.("connecting");
    const run = lookup(runId);
    const timer = setInterval(tick, 100);
    function tick() {
      if (stopped) return;
      if (!run) {
        stop();
        h.onError?.({ code: "RUN_NOT_FOUND", message: "This run does not exist.", retryable: false });
        h.onState?.("closed");
        return;
      }
      const fresh = registry()[runId] ?? run; // answers recorded since the stream opened
      for (const e of releasedEvents(runId, fresh)) {
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

  async postChoice(runId, choiceId, answer) {
    await wait(mockConfig.latencyMs);
    const run = lookup(runId);
    if (!run) fail({ error: { code: "RUN_NOT_FOUND", message: "This run does not exist.", retryable: false, details: {} } }, 404);
    const events = releasedEvents(runId, run);
    const resolved = events.some((e) => e.type === "choice_resolved" && e.choiceId === choiceId);
    if (resolved || run.answers[choiceId]) {
      fail({ error: { code: "VALIDATION_FAILED", message: "This choice was already answered or has expired.", retryable: false, details: {} } }, 409);
    }
    saveRun(runId, { ...run, answers: { ...run.answers, [choiceId]: { answer, at: Date.now() } } });
  },

  async getLimits(): Promise<Limits> {
    await wait(mockConfig.latencyMs);
    const cases = fx("limits").cases!;
    const capped = mockConfig.scenario === "limits_capped" || dailyCapHit;
    return cases[capped ? 1 : 0]!.response.body as unknown as Limits;
  },

  async getCreature(id): Promise<Creature> {
    await wait(mockConfig.latencyMs);
    const c = creatures()[id];
    if (!c) fail({ error: { code: "NOT_FOUND", message: "No creature with this id.", retryable: false, details: {} } }, 404);
    return withImages(c);
  },

  async getPublication(): Promise<never> {
    throw new ApiRequestError({ code: "NOT_FOUND", message: "Not in the fixtures.", retryable: false }, 404);
  },

  async getGallery(): Promise<GalleryPage> {
    await wait(mockConfig.latencyMs);
    const page = fx("gallery").response!.body as unknown as GalleryPage;
    return { items: page.items.map((i) => ({ ...i, imageUrl: img(i.imageUrl) })), nextCursor: null };
  },

  imageUrl(url) {
    return url;
  },
};

/** Test hook: forget mock runs and the daily-cap latch. */
export function resetMock(): void {
  dailyCapHit = false;
  for (const k of Object.keys(memory)) delete memory[k];
  try {
    localStorage.removeItem(REG_KEY);
  } catch {
    /* ignore */
  }
}
