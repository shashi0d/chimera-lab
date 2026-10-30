import { describe, expect, it, vi } from "vitest";
import { GraphLoadError, loadGraph } from "../../src/graph/migrate";
import { getDefinition } from "../../src/nodes/registry";

const migrators = (type: string) => {
  const def = getDefinition(type);
  return def ? { version: def.version, migrate: def.migrate } : undefined;
};

describe("graph load + migration (TASKSHEET 4.2, 7.6)", () => {
  it("migrates schema v0 (links + pos) to v1", () => {
    vi.spyOn(console, "info").mockImplementation(() => undefined);
    const r = loadGraph(
      {
        schemaVersion: 0,
        id: "old",
        nodes: [
          { id: "a", type: "image-input", pos: { x: 5, y: 6 } },
          { id: "f", type: "fusion", pos: { x: 1, y: 2 } },
        ],
        links: [{ from: "a", to: "f", toPort: "a" }],
      },
      migrators,
    );
    expect(r.migratedFrom).toBe(0);
    expect(r.graph.schemaVersion).toBe(1);
    expect(r.graph.graphId).toBe("old");
    expect(r.graph.nodes[0]?.position).toEqual({ x: 5, y: 6 });
    expect(r.graph.edges).toEqual([{ id: "e-migrated-0", source: "a", sourcePort: "out", target: "f", targetPort: "a" }]);
  });

  it("removes orphan edges and logs them", () => {
    const info = vi.spyOn(console, "info").mockImplementation(() => undefined);
    const r = loadGraph(
      {
        schemaVersion: 1,
        graphId: "g",
        nodes: [{ id: "a", type: "image-input", position: { x: 0, y: 0 } }],
        edges: [{ id: "e1", source: "a", sourcePort: "out", target: "gone", targetPort: "a" }, { bad: true }],
      },
      migrators,
    );
    expect(r.graph.edges).toHaveLength(0);
    expect(r.orphanEdgesRemoved).toBe(2);
    expect(info).toHaveBeenCalled();
  });

  it("keeps unknown node types for the placeholder", () => {
    const r = loadGraph({ schemaVersion: 1, graphId: "g", nodes: [{ id: "s", type: "style", position: { x: 0, y: 0 } }], edges: [] }, migrators);
    expect(r.unknownTypes).toEqual(["style"]);
    expect(r.graph.nodes[0]?.type).toBe("style");
  });

  it("opens a newer schema read-only", () => {
    const r = loadGraph({ schemaVersion: 99, graphId: "g", nodes: [], edges: [] }, migrators);
    expect(r.readOnly).toBe(true);
  });

  it("runs a node-level migration when the node version is old", () => {
    const r = loadGraph({ schemaVersion: 1, graphId: "g", nodes: [{ id: "n", type: "x", version: 1, position: { x: 0, y: 0 }, config: { old: 1 } }], edges: [] }, (t) =>
      t === "x" ? { version: 2, migrate: (c) => ({ config: { upgraded: (c as { old: number }).old + 1 }, data: {} }) } : undefined,
    );
    expect(r.graph.nodes[0]).toMatchObject({ version: 2, config: { upgraded: 2 } });
  });

  it("drops duplicate node ids and coerces bad positions", () => {
    const r = loadGraph(
      { schemaVersion: 1, graphId: "g", nodes: [{ id: "a", type: "fusion", position: { x: "nope" } }, { id: "a", type: "fusion" }], edges: [] },
      migrators,
    );
    expect(r.graph.nodes).toHaveLength(1);
    expect(r.graph.nodes[0]?.position).toEqual({ x: 0, y: 0 });
  });

  it.each([null, 42, "x", { schemaVersion: 1 }, { schemaVersion: 1, graphId: "g", nodes: "no", edges: [] }])("rejects corrupt input %#", (raw) => {
    expect(() => loadGraph(raw, migrators)).toThrow(GraphLoadError);
  });
});
