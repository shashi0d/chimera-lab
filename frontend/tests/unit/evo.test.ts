import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { hrefFor, parseRoute } from "../../src/app/route";
import { STREAM, streamRunEvents, toEvent } from "../../src/evo/http";
import { mockConfig, mockTransport, releasedEvents, resetMock, SPLIT_CREATURE_ID } from "../../src/evo/mock";
import { deriveRun, readCache, type RunRecord } from "../../src/evo/runs";
import { SseParser } from "../../src/evo/sse";
import type { AgentEvent, RunSnapshot } from "../../src/evo/types";
import success from "../../../docs/api_fixtures/run_success.json";
import hostTie from "../../../docs/api_fixtures/run_host_tie.json";
import queued from "../../../docs/api_fixtures/run_queued.json";
import cap from "../../../docs/api_fixtures/run_cap.json";
import runError from "../../../docs/api_fixtures/run_error.json";

const ev = (f: { events: unknown[] }) => f.events as AgentEvent[];
const rec = (events: AgentEvent[], over: Partial<RunRecord> = {}): RunRecord => ({
  runId: "r",
  snapshot: null,
  accepted: null,
  events,
  stream: "open",
  loadError: null,
  choice: { sending: false, error: null, sent: null },
  ...over,
});

describe("SSE parser (contract: id / event / data, ': ping' keep-alive)", () => {
  it("parses messages split across chunks, ignores comments, handles CRLF", () => {
    const p = new SseParser();
    expect(p.push(": ping\n\nid: 1\nevent: step\ndata: {\"a\"")).toEqual([]);
    expect(p.push(":1}\r\n\r\nid: 2\ndata: x\ndata: y\n\n")).toEqual([
      { id: "1", event: "step", data: '{"a":1}' },
      { id: "2", event: "message", data: "x\ny" },
    ]);
  });
  it("only known event types with numeric ids become events", () => {
    expect(toEvent('{"id":1,"type":"step"}')).toMatchObject({ id: 1 });
    expect(toEvent('{"id":"1","type":"step"}')).toBeNull();
    expect(toEvent('{"id":1,"type":"bogus"}')).toBeNull();
    expect(toEvent("not json")).toBeNull();
  });
});

function sseBody(events: AgentEvent[], opts: { close?: boolean } = {}): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(c) {
      c.enqueue(enc.encode(": ping\n\n"));
      for (const e of events) c.enqueue(enc.encode(`id: ${e.id}\nevent: ${e.type}\ndata: ${JSON.stringify(e)}\n\n`));
      if (opts.close !== false) c.close();
    },
  });
}

describe("http event stream (resume, reconnect, terminal)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("sends Last-Event-ID and ?after=, delivers in order, stops at the terminal event", async () => {
    const all = ev(success);
    const fetch = vi.fn(async () => new Response(sseBody(all.slice(5)), { status: 200 }));
    const got: number[] = [];
    const states: string[] = [];
    streamRunEvents("run_x", 5, { onEvent: (e) => got.push(e.id), onState: (s) => states.push(s) }, { fetch, getRun: vi.fn() });
    await vi.runAllTimersAsync();
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain("/evo/agent/runs/run_x/events?after=5");
    expect((init.headers as Record<string, string>)["Last-Event-ID"]).toBe("5");
    expect((init.headers as Record<string, string>)["X-Session-Id"]).toBeTruthy();
    expect(got).toEqual(all.slice(5).map((e) => e.id));
    expect(states.at(-1)).toBe("closed");
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("reconnects after a dropped connection from the last id it saw, never repeating an event", async () => {
    const all = ev(success);
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(sseBody(all.slice(0, 4)), { status: 200 }))
      .mockResolvedValueOnce(new Response(sseBody(all.slice(2)), { status: 200 })); // the server replays a little too much
    const got: number[] = [];
    streamRunEvents("run_x", 0, { onEvent: (e) => got.push(e.id) }, { fetch, getRun: vi.fn() });
    await vi.advanceTimersByTimeAsync(STREAM.backoffMs[0]! + 50);
    await vi.runAllTimersAsync();
    expect(got).toEqual(all.map((e) => e.id));
    expect((fetch.mock.calls[1] as unknown as [string])[0]).toContain("after=4");
  });

  it("404 ends the stream with RUN_NOT_FOUND", async () => {
    const body = JSON.stringify({ error: { code: "RUN_NOT_FOUND", message: "no", retryable: false, details: {} } });
    const fetch = vi.fn(async () => new Response(body, { status: 404 }));
    const onError = vi.fn();
    streamRunEvents("gone", 0, { onEvent: vi.fn(), onError }, { fetch, getRun: vi.fn() });
    await vi.runAllTimersAsync();
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ code: "RUN_NOT_FOUND" }));
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("a finished run whose stream replays nothing new closes instead of reconnecting forever", async () => {
    const fetch = vi.fn(async () => new Response(sseBody([]), { status: 200 }));
    const snap = { status: "succeeded", lastEventId: 3 } as RunSnapshot;
    const states: string[] = [];
    streamRunEvents("done", 3, { onEvent: vi.fn(), onState: (s) => states.push(s) }, { fetch, getRun: vi.fn(async () => snap) });
    await vi.advanceTimersByTimeAsync(5000);
    expect(states.at(-1)).toBe("closed");
    expect(fetch.mock.calls.length).toBeLessThanOrEqual(2);
  });
});

describe("deriveRun (what the trace shows)", () => {
  it("success: steps paired with their render and inspect, final pick, succeeded", () => {
    const d = deriveRun(rec(ev(success)));
    expect(d.status).toBe("succeeded");
    expect(d.finalize?.creatureId).toBe("crt_fx_b09");
    const steps = d.items.filter((i) => i.kind === "step");
    expect(steps).toHaveLength(10);
    const render = steps.find((s) => s.kind === "step" && s.data.step?.tool === "render");
    expect(render && render.kind === "step" && render.data.renders[0]?.imageId).toBe("img1");
    expect(d.verdicts.img2?.verdict).toBe("pass");
    expect(d.toolCalls).toBe(10);
  });
  it("queued: position and runs ahead, then running once started", () => {
    const evs = ev(queued);
    expect(deriveRun(rec(evs.slice(0, 1)))).toMatchObject({ status: "queued", position: 2, ahead: 2 });
    expect(deriveRun(rec(evs.slice(0, 2)))).toMatchObject({ status: "queued", position: 1, ahead: 1 });
    expect(deriveRun(rec(evs.slice(0, 3)))).toMatchObject({ status: "running", position: null });
  });
  it("host tie: needs_choice until choice_resolved; ask_user keeps its own row", () => {
    const evs = ev(hostTie);
    const i = evs.findIndex((e) => e.type === "needs_choice");
    const waiting = deriveRun(rec(evs.slice(0, i + 1)));
    expect(waiting.status).toBe("needs_choice");
    expect(waiting.pendingChoice?.options).toEqual(["tortoise", "domestic goat"]);
    const after = deriveRun(rec(evs.slice(0, i + 3)));
    expect(after.status).toBe("running");
    expect(after.pendingChoice).toBeNull();
    const choice = after.items.find((x) => x.kind === "choice");
    expect(choice && choice.kind === "choice" && choice.answer).toBe("domestic goat");
    expect(after.items.filter((x) => x.kind === "step" && x.data.step?.tool === "ask_user")).toHaveLength(1);
  });
  it("cap_reached is a notice, not the end", () => {
    const evs = ev(cap);
    const i = evs.findIndex((e) => e.type === "cap_reached");
    const d = deriveRun(rec(evs.slice(0, i + 1)));
    expect(d.status).toBe("running");
    expect(d.capNotice?.scope).toBe("renders");
    expect(deriveRun(rec(evs)).status).toBe("succeeded");
  });
  it("error is terminal and carries the code", () => {
    expect(deriveRun(rec(ev(runError)))).toMatchObject({ status: "failed", error: { code: "UPSTREAM_ERROR", retryable: true } });
  });
  it("a finished snapshot wins over a partial replay", () => {
    const snap = { status: "succeeded" } as RunSnapshot;
    expect(deriveRun(rec(ev(success).slice(0, 3), { snapshot: snap })).status).toBe("succeeded");
  });
});

describe("mock transport (every fixture reachable, clock survives reloads)", () => {
  beforeEach(() => {
    resetMock();
    mockConfig.latencyMs = 0;
    mockConfig.stepMs = 100;
    mockConfig.holdAt = null;
  });

  it("replays a run on a compressed clock with gap-free ids", async () => {
    mockConfig.scenario = "success";
    const res = await mockTransport.startRun({ mode: "realistic", sireName: "Indian pangolin", damName: "horse" });
    expect(res.kind).toBe("accepted");
    if (res.kind !== "accepted") return;
    const run = { fixture: "run_success", startedAt: Date.now() - 450, answers: {} };
    const evs = releasedEvents(res.runId, run);
    expect(evs.map((e) => e.id)).toEqual([1, 2, 3, 4]);
    expect(evs.every((e) => e.runId === res.runId)).toBe(true);
    const snap = await mockTransport.getRun(res.runId);
    expect(snap.status).toBe("running");
  });

  it("host tie waits for the answer, then continues from it", async () => {
    const run = { fixture: "run_host_tie", startedAt: Date.now() - 100 * 40, answers: {} as Record<string, { answer: string; at: number }> };
    const held = releasedEvents("r1", run);
    expect(held.at(-1)?.type).toBe("needs_choice");
    run.answers.choice_fx_1 = { answer: "tortoise", at: Date.now() - 2500 };
    const go = releasedEvents("r1", run);
    const resolved = go.find((e) => e.type === "choice_resolved");
    expect(resolved).toMatchObject({ answer: "tortoise", by: "user" });
    expect(go.at(-1)?.type).toBe("finalize");
  });

  it("an unanswered host tie expires and the agent decides (by: timeout)", () => {
    mockConfig.choiceMs = 500;
    const run = { fixture: "run_host_tie", startedAt: Date.now() - 100 * 60, answers: {} };
    const evs = releasedEvents("r2", run);
    expect(evs.find((e) => e.type === "choice_resolved")).toMatchObject({ answer: null, by: "timeout" });
    mockConfig.choiceMs = 120_000;
  });

  it("holdAt freezes the replay (screenshots mid-run)", () => {
    mockConfig.holdAt = 7;
    const evs = releasedEvents("r3", { fixture: "run_success", startedAt: Date.now() - 100_000, answers: {} });
    expect(evs.at(-1)?.id).toBe(7);
  });

  it("a fixture run id opens as a finished run", async () => {
    const snap = await mockTransport.getRun("run_fx_success");
    expect(snap).toMatchObject({ status: "succeeded", creatureId: "crt_fx_b09", lastEventId: 16 });
  });

  it("identify_choice: images get needs_choice, names start the host-tie run", async () => {
    mockConfig.scenario = "identify_choice";
    const first = await mockTransport.startRun({ mode: "realistic", sireImage: new Blob(["x"]), damImage: new Blob(["y"]) });
    expect(first).toMatchObject({ kind: "identify", choice: { slot: "sire", allowOther: true } });
    const second = await mockTransport.startRun({ mode: "realistic", sireName: "tortoise", damName: "domestic goat" });
    expect(second.kind === "accepted" && second.runId.startsWith("run_fx_host_tie")).toBe(true);
  });

  it.each([
    ["refused_human", 422, "HUMAN_DETECTED"],
    ["refused_type", 422, "UNSUPPORTED_FILE"],
    ["refused_size", 413, "FILE_TOO_LARGE"],
    ["refused_animal", 422, "NOT_AN_ANIMAL"],
    ["refused_corrupt", 422, "IMAGE_CORRUPT"],
    ["cap_daily", 429, "CAP_REACHED"],
    ["rate_limited", 429, "RATE_LIMITED"],
  ] as const)("%s → %i %s", async (scenario, status, code) => {
    mockConfig.scenario = scenario;
    await expect(mockTransport.startRun({ mode: "realistic", sireName: "a b", damName: "c d" })).rejects.toMatchObject({ status, code });
  });

  it("limits: open by default, capped after a daily cap refusal and in limits_capped", async () => {
    mockConfig.scenario = "success";
    expect((await mockTransport.getLimits()).liveRuns).toBe("open");
    mockConfig.scenario = "limits_capped";
    expect((await mockTransport.getLimits()).liveRuns).toBe("capped");
  });

  it("gallery and creatures serve fixture images from /__fixtures/", async () => {
    const g = await mockTransport.getGallery();
    expect(g.items).toHaveLength(6);
    expect(g.items[0]!.imageUrl).toBe("/__fixtures/images/b09_img2.jpg");
    const c = await mockTransport.getCreature("crt_fx_b09");
    expect(c.anatomyMap?.overlayUrl).toBe("/__fixtures/images/b09_anatomy.jpg");
    expect((await mockTransport.getCreature(SPLIT_CREATURE_ID)).finalChoice.agree).toBe(false);
    await expect(mockTransport.getCreature("nope")).rejects.toMatchObject({ code: "NOT_FOUND" });
  });
});

describe("trace cache and routes", () => {
  it("keeps only a gap-free prefix of cached events", () => {
    localStorage.setItem("chimera.trace.x", JSON.stringify([{ id: 1 }, { id: 2 }, { id: 4 }]));
    expect(readCache("x").map((e) => e.id)).toEqual([1, 2]);
  });
  it("routes round-trip through the query string", () => {
    for (const r of [{ view: "gallery" }, { view: "lab", runId: null }, { view: "lab", runId: "run_a" }, { view: "creature", creatureId: "crt_1" }] as const) {
      expect(parseRoute(hrefFor(r).replace("/", ""))).toEqual(r);
    }
  });
});
