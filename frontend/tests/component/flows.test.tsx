import { beforeEach, describe, expect, it, vi } from "vitest";
import { addImageFiles, replaceImage } from "../../src/canvas/addImages";
import { useConnectivity } from "../../src/connectivity/store";
import { useLimits, useCapped } from "../../src/evo/data";
import { setTransport } from "../../src/evo/index";
import { mockConfig, mockTransport, resetMock } from "../../src/evo/mock";
import { stopAllStreams, useEvoRuns } from "../../src/evo/runs";
import { useGraph } from "../../src/graph/store";
import { browserCodec, setImageCodec } from "../../src/nodes/image-input/codec";
import type { ImageInputData } from "../../src/nodes/image-input/types";
import { confirmIdentify, startFusion, useFusionStart } from "../../src/nodes/fusion/start";
import type { FusionData } from "../../src/nodes/fusion/types";
import { registerRunHandlers } from "../../src/nodes/registry";
import type { ResultData } from "../../src/nodes/result/types";
import { restoreGraph, writeRawAutosave } from "../../src/persistence/autosave";
import { useToasts } from "../../src/ui/toastStore";
import { renderHook } from "@testing-library/react";

const JPEG: Uint8Array<ArrayBuffer> = new Uint8Array([0xff, 0xd8, 0xff, 0xe0, ...new Array(60).fill(1)]);
const file = (name: string, bytes: Uint8Array<ArrayBuffer> = JPEG) => new File([bytes], name, { type: "image/jpeg" });

let n = 0;
beforeEach(() => {
  useGraph.getState().reset();
  useToasts.setState({ toasts: [] });
  useConnectivity.setState({ browserOnline: true, serverReachable: true, forced: null, status: "online" });
  useFusionStart.setState({ starting: {}, errors: {}, identify: null });
  useEvoRuns.setState({ runs: {} });
  useLimits.setState({ capError: null, data: null, status: "idle" });
  resetMock();
  mockConfig.latencyMs = 0;
  mockConfig.stepMs = 5;
  mockConfig.holdAt = null;
  mockConfig.scenario = "success";
  setTransport(mockTransport);
  window.history.replaceState(null, "", "/?view=lab");
  setImageCodec({
    decode: async () => ({ width: 900, height: 900, source: {} as CanvasImageSource, close: () => undefined }),
    encode: async (_s, _w, _h, type) => new Blob([`x${n++}`], { type }),
  });
  return () => {
    stopAllStreams();
    setImageCodec(browserCodec);
  };
});

const settle = (ms = 0) => new Promise((r) => setTimeout(r, ms));
const imgs = () => useGraph.getState().nodes.filter((x) => x.type === "image-input");
const fusionId = () => useGraph.getState().nodes.find((x) => x.type === "fusion")?.id as string;
const fusionData = () => useGraph.getState().nodes.find((x) => x.type === "fusion")?.data as FusionData;

describe("adding images (TASKSHEET 7.1, R1: kept on this device until a run starts)", () => {
  it("drop of 2 on an empty canvas: two ready nodes and a fusion node, both connected; nothing uploaded", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    await addImageFiles([file("lion.jpg"), file("tiger.jpg")], { x: 0, y: 0 });
    const g = useGraph.getState();
    expect(imgs()).toHaveLength(2);
    expect(g.nodes.filter((x) => x.type === "fusion")).toHaveLength(1);
    expect(g.edges.map((e) => e.targetPort).sort()).toEqual(["a", "b"]);
    expect(imgs().map((x) => (x.data as ImageInputData).status)).toEqual(["ready", "ready"]);
    expect((imgs()[0]?.data as ImageInputData).sha256).toMatch(/^[0-9a-f]{64}$/);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("3+ at once: max 2, toast explains the rest were ignored", async () => {
    await addImageFiles([file("1.jpg"), file("2.jpg"), file("3.jpg")], { x: 0, y: 0 });
    expect(imgs()).toHaveLength(2);
    expect(useToasts.getState().toasts.map((t) => t.message).join()).toMatch(/1 more was ignored/);
  });

  it("an unsupported file creates no node and toasts the accepted types", async () => {
    await addImageFiles([file("anim.gif", new Uint8Array([0x47, 0x49, 0x46, 0x38, 0x39, 0x61]))], { x: 0, y: 0 });
    expect(useGraph.getState().nodes).toHaveLength(0);
    expect(useToasts.getState().toasts[0]?.message).toMatch(/JPEG, PNG or WebP/);
  });

  it("replacing an image keeps id and edges and marks results stale", async () => {
    await addImageFiles([file("lion.jpg"), file("tiger.jpg")], { x: 0, y: 0 });
    useGraph.getState().updateNodeData(fusionId(), (d) => ({ ...d, runIds: ["run1"] }));
    const first = imgs()[0]?.id as string;
    const edgesBefore = useGraph.getState().edges.length;
    await replaceImage(first, file("fox.jpg"));
    expect(imgs()[0]?.id).toBe(first);
    expect((imgs()[0]?.data as ImageInputData).fileName).toBe("fox.jpg");
    expect(useGraph.getState().edges).toHaveLength(edgesBefore);
    expect(useGraph.getState().nodes.find((x) => x.id === fusionId())?.data.stale).toBe(true);
  });
});

describe("autosave restore (TASKSHEET 7.6)", () => {
  it("corrupt autosave is discarded with a toast", async () => {
    await writeRawAutosave("{{{ not a graph");
    await restoreGraph();
    expect(useGraph.getState().nodes).toHaveLength(0);
    expect(useToasts.getState().toasts[0]?.message).toMatch(/couldn't be read/);
  });

  it("orphan edges are removed on load with a note", async () => {
    vi.spyOn(console, "info").mockImplementation(() => undefined);
    await writeRawAutosave({ schemaVersion: 1, graphId: "g1", nodes: [{ id: "a", type: "image-input", position: { x: 0, y: 0 } }], edges: [{ id: "e", source: "a", sourcePort: "out", target: "zz", targetPort: "a" }] });
    await restoreGraph();
    expect(useGraph.getState().graphId).toBe("g1");
    expect(useGraph.getState().edges).toHaveLength(0);
    expect(useToasts.getState().toasts[0]?.message).toMatch(/Removed 1 broken connection/);
  });

  it("v1 canvases migrate: images keep their local copy, old pipeline runs and versions are dropped", async () => {
    await writeRawAutosave({
      schemaVersion: 1,
      graphId: "old",
      nodes: [
        { id: "a", type: "image-input", version: 1, position: { x: 0, y: 0 }, config: {}, data: { fileName: "lion.jpg", blobKey: "k", assetId: "ast", upload: { status: "done", progress: 1 } } },
        { id: "f", type: "fusion", version: 2, position: { x: 0, y: 0 }, config: { donors: { head: "A" } }, data: { activeRunId: "run_v1", runIds: ["run_v1"] } },
        { id: "r", type: "result", version: 1, position: { x: 0, y: 0 }, config: {}, data: { versions: [{ runId: "run_v1" }], selected: 0 } },
        { id: "c", type: "field-card", version: 1, position: { x: 0, y: 0 }, config: {}, data: {} },
      ],
      edges: [],
    });
    await restoreGraph();
    const byId = Object.fromEntries(useGraph.getState().nodes.map((x) => [x.id, x]));
    expect(byId.a?.data).toMatchObject({ status: "ready", blobKey: "k" });
    expect(byId.f?.config).toEqual({ mode: "realistic" });
    expect(byId.f?.data).toMatchObject({ activeRunId: null, runIds: [] });
    expect((byId.r?.data as ResultData).versions).toEqual([]);
    expect(byId.c?.type).toBe("field-card"); // kept for the "unsupported" placeholder
  });
});

describe("making a creature through the agent API (contract POST /evo/agent/runs)", () => {
  it("typed names only: posts the names, attaches the run, puts its id in the URL, and the finished creature becomes a Result version", async () => {
    const stop = registerRunHandlers();
    const spy = vi.spyOn(mockTransport, "startRun");
    await addImageFiles([], { x: 0, y: 0 });
    useGraph.getState().addNode({ id: "f", type: "fusion", version: 3, position: { x: 0, y: 0 }, config: { mode: "mythic" }, data: { activeRunId: null, runIds: [], names: { a: " Indian  pangolin ", b: "horse" } } });
    await startFusion("f");
    expect(spy).toHaveBeenCalledWith({ mode: "mythic", sireName: "Indian pangolin", damName: "horse" });
    const runId = fusionData().activeRunId as string;
    expect(runId).toMatch(/^run_fx_success-/);
    expect(window.location.search).toBe(`?run=${encodeURIComponent(runId)}`);
    expect(useGraph.getState().nodes.filter((x) => x.type === "result")).toHaveLength(1);
    await vi.waitFor(() => expect(useEvoRuns.getState().runs[runId]?.stream).toBe("closed"), { timeout: 3000 });
    const res = useGraph.getState().nodes.find((x) => x.type === "result")?.data as ResultData;
    expect(res.versions).toEqual([expect.objectContaining({ runId, creatureId: "crt_fx_b09", title: "Indian pangolin × horse" })]);
    stop();
  });

  it("photos: each slot sends its prepared image; identified names land on the photo nodes", async () => {
    const spy = vi.spyOn(mockTransport, "startRun");
    await addImageFiles([file("a.jpg"), file("b.jpg")], { x: 0, y: 0 });
    await startFusion(fusionId());
    const input = spy.mock.calls[0]![0];
    // (fake-indexeddb clones the Blob into a plain object; the browser keeps it a Blob)
    expect(input.sireImage).toBeTruthy();
    expect(input.damImage).toBeTruthy();
    expect(input).not.toHaveProperty("sireName", expect.anything());
    expect(imgs().map((x) => (x.data as ImageInputData).species)).toEqual(["Indian pangolin", "horse"]);
  });

  it.each([
    ["refused_human", "HUMAN_DETECTED", /person/],
    ["refused_animal", "NOT_AN_ANIMAL", /refused/],
    ["refused_type", "UNSUPPORTED_FILE", /refused/],
    ["refused_size", "FILE_TOO_LARGE", /refused/],
    ["refused_corrupt", "IMAGE_CORRUPT", /refused/],
  ] as const)("%s: the error is kept on the node and the sire photo is flagged", async (scenario, code, flag) => {
    mockConfig.scenario = scenario;
    await addImageFiles([file("a.jpg"), file("b.jpg")], { x: 0, y: 0 });
    await startFusion(fusionId());
    expect(useFusionStart.getState().errors[fusionId()]?.code).toBe(code);
    expect(imgs().map((x) => (x.data as ImageInputData).flagged ?? null)).toEqual([expect.stringMatching(flag), null]);
    expect(fusionData().activeRunId ?? null).toBeNull();
  });

  it("429 CAP_REACHED switches the app to the capped state", async () => {
    mockConfig.scenario = "cap_daily";
    useGraph.getState().addNode({ id: "f", type: "fusion", version: 3, position: { x: 0, y: 0 }, config: { mode: "realistic" }, data: { names: { a: "lion", b: "tiger" } } });
    await startFusion("f");
    expect(useFusionStart.getState().errors.f?.code).toBe("CAP_REACHED");
    const { result } = renderHook(() => useCapped());
    expect(result.current).toMatchObject({ capped: true, resetsAt: "2026-11-03T00:00:00Z" });
  });

  it("identify choice: no run yet; confirming posts again with names only", async () => {
    mockConfig.scenario = "identify_choice";
    const spy = vi.spyOn(mockTransport, "startRun");
    await addImageFiles([file("a.jpg"), file("b.jpg")], { x: 0, y: 0 });
    await startFusion(fusionId());
    expect(useFusionStart.getState().identify).toMatchObject({ choice: { slot: "sire" } });
    expect(fusionData().activeRunId ?? null).toBeNull();
    await confirmIdentify("Galápagos tortoise");
    expect(spy.mock.calls[1]![0]).toEqual({ mode: "realistic", sireName: "Galápagos tortoise", damName: "domestic goat" });
    expect(fusionData().activeRunId).toMatch(/^run_fx_host_tie-/);
  });

  it("a double click starts one run", async () => {
    const spy = vi.spyOn(mockTransport, "startRun");
    useGraph.getState().addNode({ id: "f", type: "fusion", version: 3, position: { x: 0, y: 0 }, config: { mode: "realistic" }, data: { names: { a: "lion", b: "tiger" } } });
    await Promise.all([startFusion("f"), startFusion("f")]);
    expect(spy).toHaveBeenCalledTimes(1);
    await settle(10);
  });
});
