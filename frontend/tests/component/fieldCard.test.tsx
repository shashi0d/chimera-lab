import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../src/api/client";
import { useConnectivity } from "../../src/connectivity/store";
import { checkConnection } from "../../src/graph/edgeRules";
import { useGraph } from "../../src/graph/store";
import type { GraphNode } from "../../src/graph/types";
import * as png from "../../src/nodes/field-card/renderPng";
import { portsOf, registerRunHandlers } from "../../src/nodes/registry";
import { useRuns } from "../../src/runs/store";
import type { FieldCard, Run } from "../../src/types/api";
import { edge, result, seed } from "../unit/helpers";
import { renderNode } from "./render";

const CARD: FieldCard = {
  commonName: "Lioiger",
  binomial: "Panthera tigroides",
  habitat: "forest, grassland, savanna",
  diet: "carnivore",
  size: "Parents: Lion 126-272 kg; Tiger 65-306 kg.",
  behaviour: "Moves like a tiger.",
  provenance: "Generated fusion. Not a real animal. Its parents have a documented real hybrid, the Liger.",
};
const v = (n: number) => ({ runId: `run${n}`, assetId: `a${n}`, creatureId: `crt${n}`, imageUrl: `/assets/a${n}/content`, spec: {} as never, createdAt: "" });
const cardNode = (data: Record<string, unknown> = {}): GraphNode => ({
  id: "c", type: "field-card", version: 1, position: { x: 0, y: 0 }, config: {}, data: { activeRunId: null, runIds: [], card: null, ...data },
});

beforeEach(() => {
  useConnectivity.setState({ browserOnline: true, serverReachable: true, forced: null, status: "online" });
  useRuns.setState({ runs: {}, startErrors: {}, starting: {}, transport: { watch: () => ({ stop: () => undefined }) } });
});

describe("F2 field card", () => {
  it("Result → Field card is a legal connection; image → card is not", () => {
    const g = { nodes: [result("r"), cardNode(), { ...cardNode(), id: "i", type: "image-input" }], edges: [] };
    expect(checkConnection(g, { source: "r", sourcePort: "out", target: "c", targetPort: "in" }, portsOf).ok).toBe(true);
    expect(checkConnection(g, { source: "i", sourcePort: "out", target: "c", targetPort: "in" }, portsOf).ok).toBe(false);
  });

  it("without a Result, or before fusing, Write card is disabled with a hint", () => {
    seed([cardNode()]);
    const { unmount } = renderNode("c");
    expect(screen.getByRole("button", { name: "Write card" })).toBeDisabled();
    expect(screen.getByText("Connect a Result to write its card.")).toBeInTheDocument();
    unmount();
    seed([result("r"), cardNode()], [edge("r", "c", "in")]);
    renderNode("c");
    expect(screen.getByText(/Fuse first/)).toBeInTheDocument();
  });

  it("writes a card: success stores it in the node and renders provenance", async () => {
    const stop = registerRunHandlers();
    let onUpdate: (r: Run) => void = () => undefined;
    useRuns.setState({ transport: { watch: (_id, cb) => ((onUpdate = cb), { stop: () => undefined }) } });
    seed([result("r", { versions: [v(1)], selected: 0 }), cardNode()], [edge("r", "c", "in")]);
    const base = { id: "run_c", graphId: "g", nodeId: "c", sessionId: null, steps: [], error: null, failedInput: null, createdAt: "", updatedAt: "", version: 1 };
    vi.spyOn(api, "startRun").mockResolvedValue({ ...base, status: "queued", result: null });
    renderNode("c");
    await userEvent.click(screen.getByRole("button", { name: "Write card" }));
    onUpdate({ ...base, status: "succeeded", version: 3, result: { assetId: "a1", creatureId: "crt1", imageUrl: "/assets/a1/content", spec: { name: "Lioiger", parents: [] } as never, card: CARD } });
    expect(await screen.findByRole("heading", { name: "Lioiger" })).toBeInTheDocument();
    expect(screen.getByText("Panthera tigroides")).toBeInTheDocument();
    expect(screen.getByText("invented name")).toBeInTheDocument();
    expect(screen.getByText(/Generated fusion. Not a real animal./)).toBeInTheDocument();
    expect(screen.getByText(/Lion 126-272 kg/)).toBeInTheDocument();
    stop();
  });

  it("is out of date when the Result switches version, and offers a rewrite", () => {
    seed([result("r", { versions: [v(1), v(2)], selected: 1 }), cardNode({ card: CARD, creatureId: "crt1", imageUrl: "/x", name: "Lioiger" })], [edge("r", "c", "in")]);
    renderNode("c");
    expect(screen.getByText("Written for v1; the Result now shows v2.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Rewrite for v2" })).toBeEnabled();
  });

  it("Download PNG works offline (client-side render)", async () => {
    useConnectivity.getState().setBrowserOnline(false);
    const render = vi.spyOn(png, "renderCardPng").mockResolvedValue(new Blob(["png"], { type: "image/png" }));
    const dl = vi.spyOn(png, "downloadBlob").mockImplementation(() => undefined);
    seed([result("r", { versions: [v(1)], selected: 0 }), cardNode({ card: CARD, creatureId: "crt1", imageUrl: "/x" })], [edge("r", "c", "in")]);
    renderNode("c");
    expect(screen.getByRole("button", { name: /Rewrite/ })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Download PNG" }));
    expect(render).toHaveBeenCalledWith(CARD, "/x");
    expect(dl).toHaveBeenCalledWith(expect.any(Blob), "lioiger-field-card.png");
  });

  it("Make field card from a Result adds a connected card (once)", async () => {
    seed([result("r", { versions: [v(1)], selected: 0 })]);
    renderNode("r");
    await userEvent.click(screen.getByRole("button", { name: "Make field card" }));
    await userEvent.click(screen.getByRole("button", { name: "Make field card" }));
    const g = useGraph.getState();
    expect(g.nodes.filter((n) => n.type === "field-card")).toHaveLength(1);
    expect(g.edges).toEqual([expect.objectContaining({ source: "r", sourcePort: "out", targetPort: "in" })]);
  });
});
