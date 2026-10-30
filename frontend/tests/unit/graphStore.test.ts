import { beforeEach, describe, expect, it } from "vitest";
import { useGraph } from "../../src/graph/store";
import { edge, fusion, img, result, seed } from "./helpers";

beforeEach(() => useGraph.getState().reset());

describe("graph store: undo/redo (P1-02)", () => {
  it("undoes and redoes add, move and delete", () => {
    const g = useGraph.getState;
    g().addNode(img("a"));
    g().moveNode("a", { x: 50, y: 60 }, { commit: true });
    g().removeNodes(["a"]);
    expect(g().nodes).toHaveLength(0);
    g().undo();
    expect(g().nodes[0]?.position).toEqual({ x: 50, y: 60 });
    g().undo();
    expect(g().nodes[0]?.position).toEqual({ x: 0, y: 0 });
    g().undo();
    expect(g().nodes).toHaveLength(0);
    g().redo();
    g().redo();
    expect(g().nodes[0]?.position).toEqual({ x: 50, y: 60 });
  });

  it("keeps at least 50 undo steps", () => {
    const g = useGraph.getState;
    g().addNode(img("a"));
    for (let i = 1; i <= 60; i++) g().moveNode("a", { x: i, y: 0 }, { commit: true });
    for (let i = 0; i < 55; i++) g().undo();
    expect(g().nodes[0]?.position.x).toBe(5);
  });

  it("deleting a node removes its edges in one step", () => {
    seed([img("a"), fusion("f")], [edge("a", "f", "a")]);
    useGraph.getState().removeNodes(["a"]);
    expect(useGraph.getState().edges).toHaveLength(0);
    useGraph.getState().undo();
    expect(useGraph.getState().edges).toHaveLength(1);
  });

  it("undo never rewinds live data such as upload progress", () => {
    const g = useGraph.getState;
    g().addNode(img("a", { upload: { status: "uploading", progress: 0.1 } }));
    g().moveNode("a", { x: 9, y: 9 }, { commit: true });
    g().updateNodeData("a", (d) => ({ ...d, upload: { status: "done", progress: 1 } }));
    g().undo();
    expect(g().nodes[0]?.position).toEqual({ x: 0, y: 0 });
    expect((g().nodes[0]?.data as { upload: { status: string } }).upload.status).toBe("done");
  });

  it("read-only graphs ignore edits", () => {
    useGraph.getState().load({ schemaVersion: 2, graphId: "g", nodes: [img("a")], edges: [] }, { readOnly: true });
    useGraph.getState().removeNodes(["a"]);
    expect(useGraph.getState().nodes).toHaveLength(1);
  });

  it("marks downstream results stale (7.1 replace image)", () => {
    seed([img("a"), fusion("f", { runIds: ["run1"] }), result("r", { versions: [{ runId: "run1" }] })], [edge("a", "f", "a"), edge("f", "r", "in")]);
    useGraph.getState().markDownstreamStale("a");
    const nodes = useGraph.getState().nodes;
    expect(nodes.find((n) => n.id === "f")?.data.stale).toBe(true);
    expect(nodes.find((n) => n.id === "r")?.data.stale).toBe(true);
    expect(nodes.find((n) => n.id === "a")?.data.stale).toBeUndefined();
  });

  it("serialises to a versioned document", () => {
    seed([img("a")]);
    expect(useGraph.getState().toDoc()).toMatchObject({ schemaVersion: 1, graphId: "g-test", nodes: [{ id: "a" }], edges: [] });
  });
});
