import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setTestSession } from "../../src/auth/auth";
import { hrefFor, parseRoute } from "../../src/app/route";
import { STREAM, streamRunEvents, toEvent } from "../../src/evo/http";
import { mockConfig, mockTransport, resetMock, runEvents } from "../fakes/evoTransport";
import { deriveRun, readCache, type RunRecord } from "../../src/evo/runs";
import { SseParser } from "../../src/evo/sse";
import type { AgentEvent, Parent, RunSnapshot } from "../../src/evo/types";

const lion: Parent = { commonName: "lion", scientificName: null, source: "name", confidence: null };
const eagle: Parent = { commonName: "golden eagle", scientificName: null, source: "name", confidence: null };
const success = runEvents("success", "r", lion, eagle);
const queued = runEvents("queued", "r", lion, eagle);
const runError = runEvents("error", "r", lion, eagle);
const rec = (events: AgentEvent[], over: Partial<RunRecord> = {}): RunRecord => ({
  runId: "r",
  snapshot: null,
  accepted: null,
  events,
  stream: "open",
  loadError: null,
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

  it("sends the access token, Last-Event-ID and ?after=, delivers in order, stops at the terminal event", async () => {
    setTestSession({ id: "user-1", email: "a@example.test" });
    const all = success;
    const fetch = vi.fn(async () => new Response(sseBody(all.slice(1)), { status: 200 }));
    const got: number[] = [];
    const states: string[] = [];
    streamRunEvents("run_x", 1, { onEvent: (e) => got.push(e.id), onState: (s) => states.push(s) }, { fetch, getRun: vi.fn() });
    await vi.runAllTimersAsync();
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain("/evo/agent/runs/run_x/events?after=1");
    expect((init.headers as Record<string, string>)["Last-Event-ID"]).toBe("1");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
    expect(got).toEqual(all.slice(1).map((e) => e.id));
    expect(states.at(-1)).toBe("closed");
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("reconnects after a dropped connection from the last id it saw, never repeating an event", async () => {
    const all = success;
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(sseBody(all.slice(0, 2)), { status: 200 }))
      .mockResolvedValueOnce(new Response(sseBody(all.slice(1)), { status: 200 })); // the server replays a little too much
    const got: number[] = [];
    streamRunEvents("run_x", 0, { onEvent: (e) => got.push(e.id) }, { fetch, getRun: vi.fn() });
    await vi.advanceTimersByTimeAsync(STREAM.backoffMs[0]! + 50);
    await vi.runAllTimersAsync();
    expect(got).toEqual(all.map((e) => e.id));
    expect((fetch.mock.calls[1] as unknown as [string])[0]).toContain("after=2");
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

describe("deriveRun (what the Fusion node and image card show)", () => {
  it("success: the image, the creature, succeeded", () => {
    const d = deriveRun(rec(success));
    expect(d.status).toBe("succeeded");
    expect(d.finalize?.creatureId).toBe("crt_r");
    expect(d.images.map((i) => i.imageId)).toEqual(["img1"]);
    expect(d.sire?.commonName).toBe("lion");
  });
  it("queued: position and runs ahead, then running once started", () => {
    expect(deriveRun(rec(queued.slice(0, 1)))).toMatchObject({ status: "queued", position: 2, ahead: 2 });
    expect(deriveRun(rec(queued.slice(0, 2)))).toMatchObject({ status: "running", position: null, ahead: null });
  });
  it("error is terminal and carries the code", () => {
    expect(deriveRun(rec(runError))).toMatchObject({ status: "failed", error: { code: "UPSTREAM_TIMEOUT", retryable: true } });
  });
  it("a finished snapshot wins over a partial replay", () => {
    const snap = { status: "succeeded" } as RunSnapshot;
    expect(deriveRun(rec(success.slice(0, 2), { snapshot: snap })).status).toBe("succeeded");
  });
});

describe("mock transport", () => {
  beforeEach(() => {
    resetMock();
    mockConfig.latencyMs = 0;
    mockConfig.stepMs = 20;
  });

  it("a run replays to its finalize event", async () => {
    const res = await mockTransport.startRun({ sireName: "lion", damName: "golden eagle" });
    expect(res.kind).toBe("accepted");
    const runId = res.kind === "accepted" ? res.runId : "";
    const got: AgentEvent[] = [];
    await new Promise<void>((done) => mockTransport.streamEvents(runId, 0, { onEvent: (e) => got.push(e), onState: (st) => st === "closed" && done() }));
    expect(got.map((e) => e.type)).toEqual(["started", "step", "render", "finalize"]);
    expect((await mockTransport.getRun(runId)).status).toBe("succeeded");
  });

  it("identify_choice: a photo gets a question, names start a run", async () => {
    mockConfig.scenario = "identify_choice";
    const photo = await mockTransport.startRun({ sireImage: new Blob(["x"]), damImage: new Blob(["y"]) });
    expect(photo.kind).toBe("identify");
    const named = await mockTransport.startRun({ sireName: "Galápagos tortoise", damName: "domestic goat" });
    expect(named.kind).toBe("accepted");
  });

  it("limits: open by default, capped after a daily cap refusal", async () => {
    expect((await mockTransport.getLimits()).liveRuns).toBe("open");
    mockConfig.scenario = "cap_daily";
    await expect(mockTransport.startRun({ sireName: "a", damName: "b" })).rejects.toMatchObject({ code: "CAP_REACHED" });
    mockConfig.scenario = "success";
    expect((await mockTransport.getLimits()).liveRuns).toBe("capped");
  });

  it("an unknown run is not found", async () => {
    await expect(mockTransport.getRun("nope")).rejects.toMatchObject({ code: "RUN_NOT_FOUND" });
  });
});

describe("event cache and routes", () => {
  it("keeps only a gap-free prefix of cached events", () => {
    localStorage.setItem("chimera.trace.x", JSON.stringify([{ id: 1 }, { id: 2 }, { id: 4 }]));
    expect(readCache("x").map((e) => e.id)).toEqual([1, 2]);
  });
  it("routes round-trip through the query string", () => {
    for (const r of [{ view: "home" }, { view: "chimeras" }, { view: "lab", runId: null, workspaceId: "ws_1" }, { view: "lab", runId: "run_a", workspaceId: "ws_1" }] as const) {
      expect(parseRoute(hrefFor(r).replace("/", ""))).toEqual(r);
    }
    expect(parseRoute("?run=run_a")).toEqual({ view: "lab", runId: "run_a", workspaceId: null }); // an old run link
    expect(parseRoute("?creature=crt_1")).toEqual({ view: "home" }); // old gallery links open the home page
  });
});
