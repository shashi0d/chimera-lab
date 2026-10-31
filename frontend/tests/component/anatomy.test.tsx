import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { useConnectivity } from "../../src/connectivity/store";
import { loadGraph } from "../../src/graph/migrate";
import { useGraph } from "../../src/graph/store";
import { getDefinition } from "../../src/nodes/registry";
import { useRuns } from "../../src/runs/store";
import { edge, fusion, img, result, seed } from "../unit/helpers";
import { renderNode } from "./render";

const migrators = (type: string) => {
  const def = getDefinition(type);
  return def ? { version: def.version, migrate: def.migrate } : undefined;
};

beforeEach(() => {
  useConnectivity.setState({ browserOnline: true, serverReachable: true, forced: null, status: "online" });
  useRuns.setState({ runs: {}, startErrors: {}, starting: {} });
});

describe("F1 anatomy controls", () => {
  it("cycles a part Auto → A → B → Auto and announces it", async () => {
    seed([img("a"), img("b"), fusion("f")], [edge("a", "f", "a"), edge("b", "f", "b")]);
    renderNode("f");
    const head = screen.getByRole("button", { name: "Head from Auto (model decides)" });
    await userEvent.click(head);
    expect(screen.getByRole("button", { name: "Head from A" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Head from A" }));
    expect(screen.getByRole("button", { name: "Head from B" })).toHaveClass("body-region--b");
    expect((useGraph.getState().nodes.find((n) => n.id === "f")?.config as { donors: Record<string, string> }).donors.head).toBe("B");
    await userEvent.click(screen.getByRole("button", { name: "Head from B" }));
    expect(screen.getByRole("button", { name: "Head from Auto (model decides)" })).toBeInTheDocument();
  });

  it("each change is one undo step", async () => {
    seed([img("a"), img("b"), fusion("f")], [edge("a", "f", "a"), edge("b", "f", "b")]);
    renderNode("f");
    await userEvent.click(screen.getByRole("button", { name: /^Tail from/ }));
    useGraph.getState().undo();
    expect((useGraph.getState().nodes.find((n) => n.id === "f")?.config as { donors?: Record<string, string> }).donors?.tail ?? "auto").toBe("auto");
  });

  it("changing a pin after a result marks the result outdated", async () => {
    seed(
      [img("a"), img("b"), fusion("f", { runIds: ["run1"] }), result("r", { versions: [{ runId: "run1" }] })],
      [edge("a", "f", "a"), edge("b", "f", "b"), edge("f", "r", "in")],
    );
    renderNode("f");
    await userEvent.click(screen.getByRole("button", { name: /^Body from/ }));
    const nodes = useGraph.getState().nodes;
    expect(nodes.find((n) => n.id === "r")?.data.stale).toBe(true);
    expect(nodes.find((n) => n.id === "f")?.data.stale).toBe(true);
  });

  it("all parts from one parent shows an advisory hint but Fuse stays enabled", () => {
    const f = fusion("f");
    f.config = { donors: { head: "A", body: "A", limbs: "A", covering: "A", tail: "A" } };
    seed([img("a"), img("b"), f], [edge("a", "f", "a"), edge("b", "f", "b")]);
    renderNode("f");
    expect(screen.getByText(/Every part comes from A/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fuse" })).toBeEnabled();
  });

  it("v1 Fusion nodes migrate to v2 with every part on Auto; bad values are sanitised", () => {
    const r = loadGraph(
      {
        schemaVersion: 1,
        graphId: "g",
        nodes: [
          { id: "f1", type: "fusion", version: 1, position: { x: 0, y: 0 }, config: {}, data: { runIds: ["x"] } },
          { id: "f2", type: "fusion", version: 1, position: { x: 0, y: 0 }, config: { donors: { head: "C", body: "B" } } },
        ],
        edges: [],
      },
      migrators,
    );
    expect(r.graph.nodes[0]).toMatchObject({ version: 2, config: { donors: { head: "auto", tail: "auto" } }, data: { runIds: ["x"] } });
    expect(r.graph.nodes[1]?.config).toEqual({ donors: { head: "auto", body: "B", limbs: "auto", covering: "auto", tail: "auto" } });
  });
});
