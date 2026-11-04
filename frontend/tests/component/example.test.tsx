import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { parseRoute } from "../../src/app/route";
import { setTestSession } from "../../src/auth/auth";
import { EXAMPLE_IDS, exampleGraph, exampleVersion } from "../../src/example/example";
import { startOwnWorkspace, Tour } from "../../src/example/Tour";
import { hasToured, TOUR_STEPS, useTour } from "../../src/example/tourStore";
import { useGraph } from "../../src/graph/store";
import { labApi } from "../../src/lab/api";
import { ToolsPanel } from "../../src/lab/ToolsPanel";
import { useLab } from "../../src/lab/store";
import { useWorkspaces } from "../../src/persistence/workspaces";
import { renderInFlow } from "./render";

beforeEach(() => {
  localStorage.clear();
  useGraph.getState().reset();
  useTour.setState({ active: false, step: 0 });
  useLab.setState({ jobs: {}, limits: null, starting: {} });
  setTestSession({ id: "user-1" });
  vi.spyOn(labApi, "limits").mockResolvedValue({ used: 0, limit: null, totalUsed: 0, totalLimit: null, resetsAt: "2026-11-05T00:00:00Z" });
  window.history.replaceState(null, "", "/");
});

describe("the example workspace", () => {
  it("is Fusion (Tiger + Bat, anime) → its image → a ready animal card, served as static files", () => {
    const g = exampleGraph();
    expect(g.nodes.map((n) => n.type)).toEqual(["fusion", "version", "card"]);
    expect(g.nodes[0]!.config).toMatchObject({ style: "anime" });
    expect(g.nodes[0]!.data).toMatchObject({ names: { a: "Tiger", b: "Bat" } });
    expect(exampleVersion.imageUrl).toBe("/example/tiger-bat.webp");
    expect(exampleVersion.card?.status).toBe("ready");
    expect(exampleVersion.card?.angles).toHaveLength(4);
    expect(exampleVersion.card?.angles.every((a) => a.url.startsWith("/example/"))).toBe(true);
    expect(g.edges.map((e) => [e.source, e.target])).toEqual([[EXAMPLE_IDS.fusion, EXAMPLE_IDS.version], [EXAMPLE_IDS.version, EXAMPLE_IDS.card]]);
  });

  it("shows the image tools but keeps them disabled: the example is read-only", () => {
    useGraph.getState().load(exampleGraph(), { readOnly: true });
    renderInFlow(<ToolsPanel nodeId={EXAMPLE_IDS.version} />);
    expect(screen.getByText(/This is the example/)).toBeInTheDocument();
    for (const name of [/Revise/, /Paint an area/, /Draw on it/, /Save/, /Delete/]) {
      expect(screen.getByRole("button", { name })).toBeDisabled();
    }
  });
});

describe("the guided tour", () => {
  it("walks through the example step by step, selecting each part, and ends on Chimeras", async () => {
    const user = userEvent.setup();
    useGraph.getState().load(exampleGraph(), { readOnly: true });
    renderInFlow(<Tour />);
    useTour.getState().start();
    expect(await screen.findByRole("heading", { name: "Pick two animals" })).toBeInTheDocument();
    expect(parseRoute(window.location.search)).toMatchObject({ view: "lab", workspaceId: "example" });
    expect(useGraph.getState().selection).toEqual([EXAMPLE_IDS.fusion]);

    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("heading", { name: "The creature arrives" })).toBeInTheDocument();
    expect(useGraph.getState().selection).toEqual([EXAMPLE_IDS.version]);

    await user.click(screen.getByRole("button", { name: "Next" }));
    const tools = screen.getByRole("heading", { name: "Change anything" }).closest("section")!;
    expect(within(tools).getByText("Paint an area:")).toBeInTheDocument();
    expect(within(tools).getByText("Draw on it:")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(useGraph.getState().selection).toEqual([EXAMPLE_IDS.card]);
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("heading", { name: "Your collection" })).toBeInTheDocument();
    expect(parseRoute(window.location.search)).toEqual({ view: "chimeras" });

    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("button", { name: "Start your own workspace" })).toBeInTheDocument();
    expect(useTour.getState().step).toBe(TOUR_STEPS.length - 1);
  });

  it("Skip closes it for good", async () => {
    const user = userEvent.setup();
    renderInFlow(<Tour />);
    useTour.getState().start();
    await user.click(await screen.findByRole("button", { name: "Skip tour" }));
    expect(screen.queryByRole("heading", { name: "Pick two animals" })).toBeNull();
    expect(hasToured()).toBe(true);
  });

  it("Start your own workspace creates one, opens it and ends the tour", async () => {
    const create = vi.spyOn(labApi, "createWorkspace").mockResolvedValue({ id: "ws_new", name: "My first creature", createdAt: "", updatedAt: "" });
    useTour.getState().start();
    await startOwnWorkspace();
    expect(create).toHaveBeenCalledWith("My first creature");
    expect(useWorkspaces.getState().currentId).toBe("ws_new");
    expect(parseRoute(window.location.search)).toMatchObject({ view: "lab", workspaceId: "ws_new" });
    expect(useTour.getState().active).toBe(false);
    expect(hasToured()).toBe(true);
  });
});
