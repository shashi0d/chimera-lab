import { act, fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { parseRoute } from "../../src/app/route";
import { setTestSession } from "../../src/auth/auth";
import { evo, setTransport } from "../../src/evo/index";
import { stopAllStreams, useEvoRuns } from "../../src/evo/runs";
import { useGraph } from "../../src/graph/store";
import { labApi, type LabVersion } from "../../src/lab/api";
import { createNode, registerRunHandlers } from "../../src/nodes/registry";
import type { VersionData } from "../../src/nodes/version/types";
import { useWorkspaces } from "../../src/persistence/workspaces";
import { GardenPage } from "../../src/screens/GardenPage";
import { CARD_MS, REPLAY, TUTORIAL_VERSION, TUTORIAL_WS } from "../../src/tutorial/sandbox";
import { Tour } from "../../src/tutorial/Tour";
import { hasToured, tourPrefill, useTour } from "../../src/tutorial/tourStore";
import { mockTransport, resetMock } from "../fakes/evoTransport";
import { renderInFlow, renderNode } from "./render";

const fetchSpy = vi.fn(async () => new Response(JSON.stringify({ chimeras: [] }), { status: 200, headers: { "Content-Type": "application/json" } }));

beforeEach(() => {
  localStorage.clear();
  useGraph.getState().reset();
  stopAllStreams();
  useEvoRuns.setState({ runs: {} });
  setTestSession({ id: "user-1" });
  resetMock();
  setTransport(mockTransport);
  useWorkspaces.setState({ userId: "user-1", list: [], currentId: TUTORIAL_WS, loaded: true });
  useTour.setState({ active: true, phase: "lab" });
  window.history.replaceState(null, "", `/?ws=${TUTORIAL_WS}`);
  fetchSpy.mockClear();
  vi.stubGlobal("fetch", fetchSpy);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  delete document.documentElement.dataset.tourTarget;
});

const step = () => screen.getByRole("heading", { level: 2 }).textContent;
const glowing = () => document.documentElement.dataset.tourTarget;

describe("the tutorial sandbox (no model calls)", () => {
  it("replays a real Fusion run: started → render → finalize, then the Tiger × Bat image as a version", async () => {
    vi.useFakeTimers();
    const res = await evo().startRun({ sireName: "Tiger", damName: "Bat", style: "anime", workspaceId: TUTORIAL_WS });
    expect(res.kind).toBe("accepted");
    const runId = (res as { runId: string }).runId;
    expect((await evo().getRun(runId)).status).toBe("running");
    const seen: string[] = [];
    evo().streamEvents(runId, 0, { onEvent: (e) => seen.push(e.type) });
    await vi.advanceTimersByTimeAsync(REPLAY.finalize + 500);
    expect(seen).toEqual(["started", "step", "render", "finalize"]);
    expect((await evo().getRun(runId)).status).toBe("succeeded");
    const v = await labApi.versionFromRun(runId, TUTORIAL_WS);
    expect(v).toMatchObject({ id: TUTORIAL_VERSION, imageUrl: "/example/tiger-bat.webp", saved: false });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("saving draws the animal card in the background and adds it to Chimeras; edits are look-only", async () => {
    vi.useFakeTimers();
    const saved = await labApi.setSaved(TUTORIAL_VERSION, true);
    expect(saved.saved).toBe(true);
    expect(saved.card?.status).toBe("running");
    await vi.advanceTimersByTimeAsync(CARD_MS + 10);
    const card = await labApi.savedCard(TUTORIAL_VERSION);
    expect(card?.status).toBe("ready");
    expect(card?.angles).toHaveLength(4);
    const list = await labApi.chimeras();
    expect(list.map((x) => x.id)).toEqual([TUTORIAL_VERSION]);
    await expect(labApi.revise(TUTORIAL_VERSION, "longer legs")).rejects.toThrow(/look around/);
    await expect(labApi.setShared(TUTORIAL_VERSION, true)).rejects.toThrow(/look around/);
    expect(fetchSpy).toHaveBeenCalledTimes(1); // only the visitor's own chimeras list
  });

  it("other workspaces are untouched: a run there goes to the real transport", async () => {
    const res = await evo().startRun({ sireName: "lion", damName: "eagle", workspaceId: "main" });
    expect((res as { runId: string }).runId).toMatch(/^run_fx_/);
  });
});

describe("the hands-on tour", () => {
  it("a Fusion added during the tour comes prefilled with Tiger, Bat and the Anime style", () => {
    expect(tourPrefill("fusion")).toEqual({ data: { names: { a: "Tiger", b: "Bat" } }, config: { style: "anime" } });
    expect(tourPrefill("edit")).toBeNull();
    useTour.setState({ active: false });
    expect(tourPrefill("fusion")).toBeNull();
  });

  it("follows the canvas: add the Fusion → Make glows → the run → Save glows → Chimeras", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const stop = registerRunHandlers();
    renderInFlow(<Tour />);
    expect(step()).toBe("Add a Fusion node");
    expect(glowing()).toBe("add-fusion");

    const pre = tourPrefill("fusion")!;
    const fusion = createNode("fusion", { x: 0, y: 0 }, pre.data);
    fusion.config = { ...fusion.config, ...pre.config };
    act(() => useGraph.getState().addNode(fusion));
    expect(step()).toBe("Make the creature");
    expect(glowing()).toBe("make");

    renderNode(fusion.id);
    const make = screen.getByRole("button", { name: /Make creature/ });
    expect(make).toHaveAttribute("data-tour", "make");
    fireEvent.click(make);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });
    expect(step()).toBe("Your creature is being made");
    expect(glowing()).toBeUndefined();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(REPLAY.finalize + 1500);
    });
    const versionNode = useGraph.getState().nodes.find((n) => n.type === "version");
    expect((versionNode?.data as VersionData).version?.imageUrl).toBe("/example/tiger-bat.webp");
    expect(step()).toBe("Here it is! Save it");
    expect(glowing()).toBe("save");
    expect(useGraph.getState().selection).toEqual([versionNode!.id]); // its toolbar shows the Save button

    await act(async () => {
      const v = await labApi.setSaved(TUTORIAL_VERSION, true);
      useGraph.getState().updateNodeData<VersionData>(versionNode!.id, (d) => ({ ...d, version: v }));
    });
    expect(step()).toBe("Open Chimeras");
    expect(glowing()).toBe("nav-chimeras");
    expect(fetchSpy).not.toHaveBeenCalled(); // the whole run: no server, no model
    stop();
  });

  it("Chimeras, then the workspaces: New workspace glows, and creating one ends the tour", async () => {
    useTour.setState({ active: true, phase: "chimeras" });
    window.history.replaceState(null, "", "/?view=chimeras");
    renderInFlow(<Tour />);
    expect(step()).toBe("Your collection");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(step()).toBe("Now it's your turn");
    expect(glowing()).toBe("nav-workspaces");
    act(() => useTour.getState().end());
    expect(useTour.getState().active).toBe(false);
    expect(hasToured()).toBe(true);
  });

  it("Skip ends it for good and goes to the workspace list", () => {
    renderInFlow(<Tour />);
    fireEvent.click(screen.getByRole("button", { name: "Skip tutorial" }));
    expect(hasToured()).toBe(true);
    expect(parseRoute(window.location.search)).toEqual({ view: "home" });
    expect(screen.queryByRole("heading", { level: 2 })).toBeNull();
  });
});

describe("the Fusion style picker", () => {
  it("shows all five styles, with Sketch instead of Drawing", () => {
    useTour.setState({ active: false });
    useWorkspaces.setState({ currentId: "main" });
    const fusion = createNode("fusion", { x: 0, y: 0 });
    useGraph.getState().addNode(fusion);
    renderNode(fusion.id);
    for (const name of ["Real", "Sketch", "Anime", "Comic", "Cartoon"]) expect(screen.getByRole("radio", { name })).toBeInTheDocument();
    expect(screen.queryByRole("radio", { name: "Drawing" })).toBeNull();
  });
});

describe("the Garden", () => {
  it("lists shared creatures from everyone and marks the visitor's own", async () => {
    const v = (id: string, mine: boolean): LabVersion => ({
      id, parentId: null, runId: null, creatureId: null, operation: "fusion", instruction: "", imageUrl: `/x/${id}.png`, createdAt: "", isFinal: false,
      title: id, mine, shared: true,
      card: { status: "ready", profile: { name: id, length: "1 m", weight: "1 kg", habitat: "h", explorers_notes: "n", trait: "T", summary: "s", accent_color: "#000000", reasoning: "" }, angles: [], error: null },
    });
    vi.spyOn(labApi, "garden").mockResolvedValue([v("Nightstripe", true), v("Scalesteed", false)]);
    renderInFlow(<GardenPage />);
    expect(await screen.findByRole("button", { name: /Nightstripe/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Scalesteed/ })).toBeInTheDocument();
    expect(screen.getAllByText("Yours")).toHaveLength(1);
  });
});

