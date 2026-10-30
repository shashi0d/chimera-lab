import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../src/api/client";
import { ApiRequestError } from "../../src/api/errors";
import { addImageFiles, replaceImage } from "../../src/canvas/addImages";
import { useConnectivity } from "../../src/connectivity/store";
import { useGraph } from "../../src/graph/store";
import { browserCodec, setImageCodec } from "../../src/nodes/image-input/codec";
import type { ImageInputData } from "../../src/nodes/image-input/types";
import { flushUploadQueue } from "../../src/nodes/image-input/uploads";
import { registerRunHandlers } from "../../src/nodes/registry";
import type { ResultData } from "../../src/nodes/result/types";
import { restoreGraph, writeRawAutosave } from "../../src/persistence/autosave";
import { useRuns } from "../../src/runs/store";
import type { Asset, CreatureSpec, Run } from "../../src/types/api";
import { useToasts } from "../../src/ui/toastStore";

const JPEG: Uint8Array<ArrayBuffer> = new Uint8Array([0xff, 0xd8, 0xff, 0xe0, ...new Array(60).fill(1)]);
const file = (name: string, bytes: Uint8Array<ArrayBuffer> = JPEG) => new File([bytes], name, { type: "image/jpeg" });
const asset = (id: string): Asset => ({ assetId: id, width: 900, height: 900, sha256: `sha-${id}`, contentType: "image/jpeg", url: `/assets/${id}/content`, createdAt: "" });

let uploads = 0;
beforeEach(() => {
  useGraph.getState().reset();
  useToasts.setState({ toasts: [] });
  useConnectivity.setState({ browserOnline: true, serverReachable: true, forced: null, status: "online" });
  setImageCodec({
    decode: async () => ({ width: 900, height: 900, source: {} as CanvasImageSource, close: () => undefined }),
    encode: async (_s, _w, _h, type) => new Blob(["x"], { type }),
  });
  uploads = 0;
  vi.spyOn(api, "uploadAsset").mockImplementation((_b, _n, onProgress) => {
    uploads++;
    onProgress(0.5);
    return { promise: Promise.resolve(asset(`ast${uploads}`)), abort: () => undefined };
  });
  return () => setImageCodec(browserCodec);
});

const settle = () => new Promise((r) => setTimeout(r, 0));
const imgs = () => useGraph.getState().nodes.filter((n) => n.type === "image-input");

describe("adding images (TASKSHEET 7.1)", () => {
  it("drop of 2 on an empty canvas: two nodes, a fusion node, both connected, uploaded", async () => {
    await addImageFiles([file("lion.jpg"), file("tiger.jpg")], { x: 0, y: 0 });
    await settle();
    const g = useGraph.getState();
    expect(imgs()).toHaveLength(2);
    expect(g.nodes.filter((n) => n.type === "fusion")).toHaveLength(1);
    expect(g.edges.map((e) => e.targetPort).sort()).toEqual(["a", "b"]);
    expect(imgs().map((n) => (n.data as ImageInputData).upload.status)).toEqual(["done", "done"]);
    expect((imgs()[0]?.data as ImageInputData).assetId).toBe("ast1");
  });

  it("3+ at once: max 2, toast explains the rest were ignored", async () => {
    await addImageFiles([file("1.jpg"), file("2.jpg"), file("3.jpg")], { x: 0, y: 0 });
    expect(imgs()).toHaveLength(2);
    expect(useToasts.getState().toasts.map((t) => t.message).join()).toMatch(/1 more was ignored/);
  });

  it("an unsupported file creates no node and toasts the accepted types", async () => {
    await addImageFiles([file("anim.gif", new Uint8Array([0x47, 0x49, 0x46, 0x38, 0x39, 0x61]))], { x: 0, y: 0 });
    expect(useGraph.getState().nodes).toHaveLength(0);
    expect(useToasts.getState().toasts[0]?.message).toMatch(/JPEG, PNG, WebP or HEIC/);
  });

  it("server rejection marks the node in error", async () => {
    vi.mocked(api.uploadAsset).mockImplementation(() => ({
      promise: Promise.reject(new ApiRequestError({ code: "IMAGE_CORRUPT", message: "x", retryable: false }, 422)),
      abort: () => undefined,
    }));
    await addImageFiles([file("bad.jpg")], { x: 0, y: 0 });
    await settle();
    expect((imgs()[0]?.data as ImageInputData).upload).toMatchObject({ status: "error", error: { code: "IMAGE_CORRUPT" } });
  });

  it("offline: uploads are queued and start on reconnect (7.7)", async () => {
    useConnectivity.getState().setBrowserOnline(false);
    await addImageFiles([file("lion.jpg")], { x: 0, y: 0 });
    await settle();
    expect((imgs()[0]?.data as ImageInputData).upload.status).toBe("queued");
    expect(uploads).toBe(0);
    useConnectivity.getState().setBrowserOnline(true);
    flushUploadQueue();
    await settle();
    await settle();
    expect((imgs()[0]?.data as ImageInputData).upload.status).toBe("done");
  });

  it("replacing an image keeps id and edges and marks results stale", async () => {
    await addImageFiles([file("lion.jpg"), file("tiger.jpg")], { x: 0, y: 0 });
    await settle();
    const fusionId = useGraph.getState().nodes.find((n) => n.type === "fusion")?.id as string;
    useGraph.getState().updateNodeData(fusionId, (d) => ({ ...d, runIds: ["run1"] }));
    const first = imgs()[0]?.id as string;
    const edgesBefore = useGraph.getState().edges.length;
    await replaceImage(first, file("fox.jpg"));
    await settle();
    expect(imgs()[0]?.id).toBe(first);
    expect((imgs()[0]?.data as ImageInputData).fileName).toBe("fox.jpg");
    expect(useGraph.getState().edges).toHaveLength(edgesBefore);
    expect(useGraph.getState().nodes.find((n) => n.id === fusionId)?.data.stale).toBe(true);
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
});

describe("run lifecycle on the canvas (P4)", () => {
  const baseRun = (over: Partial<Run>): Run => ({
    id: "run1", graphId: "g", nodeId: "f", sessionId: null, status: "queued", steps: [], result: null, error: null,
    failedInput: null, createdAt: "", updatedAt: "", version: 1, usage: {}, ...over,
  });

  it("start creates a Result node; success adds versions; re-run adds version 2", async () => {
    const stop = registerRunHandlers();
    let onUpdate: (r: Run) => void = () => undefined;
    useRuns.setState({ runs: {}, starting: {}, startErrors: {}, transport: { watch: (_id, cb) => ((onUpdate = cb), { stop: () => undefined }) } });
    await addImageFiles([file("lion.jpg"), file("tiger.jpg")], { x: 0, y: 0 });
    await settle();
    const fusionId = useGraph.getState().nodes.find((n) => n.type === "fusion")?.id as string;
    const spec = { parents: [], realHybrid: null, bodyPlan: "quadruped", partDonors: { head: "A", body: "B", limbs: "B", covering: "A", tail: "A" }, rationale: "", name: "X", warnings: [], prompt: "", model: { vision: "v", image: "i" }, donorSource: {}, realHybrids: [], mythology: [], rulesSummary: {} } satisfies CreatureSpec;

    for (const n of [1, 2]) {
      vi.spyOn(api, "startRun").mockResolvedValueOnce(baseRun({ id: `run${n}`, nodeId: fusionId }));
      await useRuns.getState().start(fusionId);
      expect(useGraph.getState().nodes.filter((x) => x.type === "result")).toHaveLength(1);
      onUpdate(baseRun({ id: `run${n}`, nodeId: fusionId, status: "succeeded", version: 5, result: { assetId: `g${n}`, creatureId: `c${n}`, imageUrl: `/assets/g${n}/content`, spec, card: null, metaResponseId: null } }));
    }
    const res = useGraph.getState().nodes.find((x) => x.type === "result")?.data as ResultData;
    expect(res.versions.map((v) => v.runId)).toEqual(["run1", "run2"]);
    expect(res.selected).toBe(1);
    // applying the same run twice (e.g. after reload) does not duplicate
    onUpdate(baseRun({ id: "run2", nodeId: fusionId, status: "succeeded", version: 6, result: { assetId: "g2", creatureId: "c2", imageUrl: "/x", spec, card: null, metaResponseId: null } }));
    expect((useGraph.getState().nodes.find((x) => x.type === "result")?.data as ResultData).versions).toHaveLength(2);
    stop();
  });

  it("NOT_AN_ANIMAL highlights the offending input node", async () => {
    const stop = registerRunHandlers();
    let onUpdate: (r: Run) => void = () => undefined;
    useRuns.setState({ runs: {}, starting: {}, startErrors: {}, transport: { watch: (_id, cb) => ((onUpdate = cb), { stop: () => undefined }) } });
    await addImageFiles([file("lion.jpg"), file("plant.jpg")], { x: 0, y: 0 });
    await settle();
    const fusionId = useGraph.getState().nodes.find((n) => n.type === "fusion")?.id as string;
    vi.spyOn(api, "startRun").mockResolvedValueOnce(baseRun({ nodeId: fusionId }));
    await useRuns.getState().start(fusionId);
    onUpdate(baseRun({ nodeId: fusionId, status: "failed", failedInput: "B", version: 4, error: { code: "NOT_AN_ANIMAL", message: "", retryable: false, retryAfterMs: null, details: {}, errorId: null } }));
    const flagged = imgs().map((n) => Boolean((n.data as ImageInputData).flagged));
    expect(flagged).toEqual([false, true]);
    stop();
  });
});
