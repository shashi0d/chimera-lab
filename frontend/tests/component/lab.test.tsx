import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { setTestSession, useAuth } from "../../src/auth/auth";
import { setTransport } from "../../src/evo/index";
import { useGraph } from "../../src/graph/store";
import { labApi, type AnimalCard, type LabJob, type LabVersion } from "../../src/lab/api";
import { addCardNode, addEditNode, addFusionFrom, addVersionNode, lineage, versionNumber } from "../../src/lab/graph";
import type { CardData } from "../../src/nodes/card/types";
import { startFusion } from "../../src/nodes/fusion/start";
import type { FusionConfig, FusionData } from "../../src/nodes/fusion/types";
import { followJobs, generateEdit, stopFollowingJobs, useLab } from "../../src/lab/store";
import { ToolsPanel } from "../../src/lab/ToolsPanel";
import type { EditData } from "../../src/nodes/edit/types";
import type { VersionData } from "../../src/nodes/version/types";
import { LabView } from "../../src/screens/LabView";
import { mockTransport, resetMock } from "../fakes/evoTransport";
import { renderInFlow, renderNode } from "./render";

const version = (id: string, over: Partial<LabVersion> = {}): LabVersion => ({
  id, parentId: null, runId: "run_1", creatureId: "crt_1", operation: "fusion", instruction: "lion × eagle (realistic)",
  imageUrl: `/evo/files/lab/${id}.png`, createdAt: "2026-11-03T00:00:00Z", isFinal: false, publicationId: null, title: "lion × eagle", ...over,
});

const job = (id: string, over: Partial<LabJob> = {}): LabJob => ({
  id, operation: "revise", status: "queued", stage: "Waiting for a model slot", parentId: "labv_1", instruction: "Longer legs",
  createdAt: "2026-11-03T00:00:00Z", updatedAt: "2026-11-03T00:00:00Z", result: null, error: null, ...over,
});

const settle = (ms = 0) => new Promise((r) => setTimeout(r, ms));
const nodesOf = (type: string) => useGraph.getState().nodes.filter((n) => n.type === type);

/** A canvas with a Fusion node and its finished V1 card. Returns the V1 card's node id. */
function withV1(): string {
  useGraph.getState().addNode({ id: "f", type: "fusion", version: 3, position: { x: 0, y: 0 }, config: { mode: "realistic" }, data: { activeRunId: null, runIds: [] } });
  return addVersionNode("f", { version: version("labv_1"), runId: null, error: null });
}

beforeEach(() => {
  useGraph.getState().reset();
  useLab.setState({ jobs: {}, limits: null, starting: {} });
  stopFollowingJobs();
  setTestSession({ id: "user-1", email: "a@example.test" });
  resetMock();
  setTransport(mockTransport);
  vi.spyOn(labApi, "limits").mockResolvedValue({ used: 1, limit: 20, totalUsed: 1, totalLimit: 100, resetsAt: "2026-11-04T00:00:00Z" });
});

describe("the Lab path (FLORA-style: image card -> edit card -> image card)", () => {
  it("an edit's finished job becomes a new image card after the edit card, once", async () => {
    const v1 = withV1();
    const edit = addEditNode(v1, "revise", "Longer legs");
    expect(useGraph.getState().edges.some((e) => e.source === v1 && e.target === edit)).toBe(true);
    const revise = vi.spyOn(labApi, "revise").mockResolvedValue(job("labjob_1"));
    const v2 = version("labv_2", { parentId: "labv_1", operation: "revise", instruction: "Longer legs" });
    const jobs = vi.spyOn(labApi, "jobs").mockResolvedValueOnce([job("labjob_1", { status: "running", stage: "Revising the image" })]).mockResolvedValue([job("labjob_1", { status: "succeeded", stage: "Ready", result: v2 })]);
    await generateEdit(edit);
    expect(revise).toHaveBeenCalledWith("labv_1", "Longer legs");
    expect((useGraph.getState().nodes.find((n) => n.id === edit)?.data as EditData).activeJobId).toBe("labjob_1");
    await vi.waitFor(() => expect(nodesOf("version")).toHaveLength(2), { timeout: 5000 });
    const card = nodesOf("version").find((n) => (n.data as VersionData).version?.id === "labv_2")!;
    expect(useGraph.getState().edges.some((e) => e.source === edit && e.target === card.id)).toBe(true);
    expect((useGraph.getState().nodes.find((n) => n.id === edit)?.data as EditData).activeJobId).toBeNull();
    expect(lineage(card.id).map((n) => (n.data as VersionData).version?.id)).toEqual(["labv_1", "labv_2"]);
    expect(versionNumber(card.id)).toBe(2);
    followJobs(); // a reload or a second poll never duplicates the card
    await settle(20);
    expect(nodesOf("version")).toHaveLength(2);
    expect(jobs).toHaveBeenCalled();
  });

  it("a failed job shows its reason on the edit card", async () => {
    const edit = addEditNode(withV1(), "revise", "Longer legs");
    vi.spyOn(labApi, "revise").mockResolvedValue(job("labjob_9"));
    vi.spyOn(labApi, "jobs").mockResolvedValue([job("labjob_9", { status: "failed", stage: "Failed", error: "The image provider is down." })]);
    await generateEdit(edit);
    await vi.waitFor(() => expect((useGraph.getState().nodes.find((n) => n.id === edit)?.data as EditData).error).toBe("The image provider is down."));
    expect(nodesOf("version")).toHaveLength(1);
    renderNode(edit);
    expect(screen.getByRole("alert")).toHaveTextContent("The image provider is down.");
    expect(screen.getByRole("button", { name: /Generate another|Generate/ })).toBeEnabled();
  });

  it("a paint edit waits for a painted area and says so", async () => {
    const edit = addEditNode(withV1(), "paint", "Blend the waist");
    const paint = vi.spyOn(labApi, "paint");
    renderNode(edit);
    expect(screen.getByText("Paint the area to change.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate" })).toBeDisabled();
    await generateEdit(edit);
    expect(paint).not.toHaveBeenCalled();
  });

  it("an edit card without an instruction can't run", () => {
    const edit = addEditNode(withV1(), "revise");
    renderNode(edit);
    expect(screen.getByText("Describe the change.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate" })).toBeDisabled();
  });

  it("the image card shows its place in the path and its change", () => {
    const v1 = withV1();
    const edit = addEditNode(v1, "revise", "Blue fur");
    const v2 = addVersionNode(edit, { version: version("labv_2", { parentId: "labv_1", operation: "revise", instruction: "Blue fur", isFinal: true }), runId: null, error: null });
    renderNode(v2);
    expect(screen.getByText("V2 · Revise")).toBeInTheDocument();
    expect(screen.getByText("Blue fur")).toBeInTheDocument();
    expect(screen.getAllByText("Final").length).toBeGreaterThan(0);
  });
});

describe("tools for the selected image", () => {
  it("shows the path, and Save keeps the creature (its card is made in the background)", async () => {
    const v1 = withV1();
    const edit = addEditNode(v1, "revise", "Blue fur");
    const v2 = addVersionNode(edit, { version: version("labv_2", { parentId: "labv_1", operation: "revise", instruction: "Blue fur" }), runId: null, error: null });
    const save = vi.spyOn(labApi, "setSaved").mockResolvedValue(version("labv_2", { parentId: "labv_1", operation: "revise", instruction: "Blue fur", saved: true }));
    renderInFlow(<ToolsPanel nodeId={v2} />);
    const path = screen.getByRole("list");
    expect(within(path).getAllByRole("listitem")).toHaveLength(2);
    expect(within(path).getByText("V2 · Revise")).toBeInTheDocument();
    expect(screen.queryByText(/gallery/i)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(save).toHaveBeenCalledWith("labv_2", true);
    await vi.waitFor(() => expect((useGraph.getState().nodes.find((n) => n.id === v2)?.data as VersionData).version?.saved).toBe(true));
  });

  it("the panel has no visual review or collaborator", () => {
    const v1 = withV1();
    renderInFlow(<ToolsPanel nodeId={v1} />);
    expect(screen.queryByText(/Visual review/i)).toBeNull();
    expect(screen.queryByText(/Collaborator/i)).toBeNull();
    expect(screen.getByRole("button", { name: "Revise" })).toBeInTheDocument();
  });
});

describe("sign-in", () => {
  it("the Lab asks to sign in", () => {
    setTestSession(null);
    renderInFlow(<LabView ready runId={null} />);
    expect(screen.getByRole("heading", { name: "Sign in to create" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Email me a sign-in link" })).toBeDisabled();
  });

  it("explains when sign-in is not configured", () => {
    useAuth.setState({ status: "unavailable", error: "Sign-in is not configured on this server." });
    renderInFlow(<LabView ready runId={null} />);
    expect(screen.getByRole("alert")).toHaveTextContent("not configured");
  });
});

describe("building on a generated image", () => {
  const profile = {
    name: "Scalesteed", length: "3 m", weight: "420 kg", habitat: "Dry savanna", explorers_notes: "It rolls its armoured tail when startled.",
    trait: "SCALES", summary: "A horse in pangolin scales.", accent_color: "#9db8f5", reasoning: "The scales read as pangolin.",
  };
  const views = ["front", "side", "back", "above"];
  const ready: AnimalCard = { status: "ready", profile, angles: views.map((v) => ({ view: v, url: `/evo/files/lab/a_${v}.png` })), error: null };

  it("an animal card is made once for its image and shows the field-guide page with four more angles", async () => {
    const v1 = withV1();
    const make = vi.spyOn(labApi, "card").mockResolvedValue({ status: "running", profile: null, angles: [], error: null });
    const saved = vi.spyOn(labApi, "savedCard").mockResolvedValue(ready);
    const id = addCardNode(v1);
    expect(useGraph.getState().edges.some((e) => e.source === v1 && e.target === id && e.targetPort === "in")).toBe(true);
    expect(addCardNode(v1)).toBe(id); // one card per image
    expect(nodesOf("card")).toHaveLength(1);
    renderNode(id);
    // On the canvas the card is small (the closed card); a click opens the full card in a modal.
    const tile = await screen.findByRole("button", { name: "Scalesteed. Open card" }, { timeout: 5000 });
    expect(make).toHaveBeenCalledTimes(1);
    expect(make).toHaveBeenCalledWith("labv_1");
    expect(saved).toHaveBeenCalledWith("labv_1");
    expect(tile.textContent).toContain("SCALES");
    expect(screen.queryByRole("dialog")).toBeNull();
    await userEvent.click(tile);
    const modal = await screen.findByRole("dialog", { name: "Scalesteed, animal card" });
    expect(modal.textContent).toMatch(/Length - 3 m\s+Weight - 420 kg/);
    expect(modal.textContent).toContain("Habitat - Dry savanna");
    expect(modal.textContent).toContain("It rolls its armoured tail when startled.");
    expect(within(modal).getAllByRole("img", { name: /Scalesteed, (front|side|back|above) view/ })).toHaveLength(4);
    await vi.waitFor(() => expect(within(modal).getByRole("group", { name: "Scalesteed card" })).toHaveAttribute("aria-expanded", "true"));
    await userEvent.click(within(modal).getByRole("button", { name: "Close the card" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("the open card's text can be edited and is saved to the server", async () => {
    const v1 = withV1();
    vi.spyOn(labApi, "card").mockResolvedValue(ready);
    const editProfile = vi.spyOn(labApi, "editProfile").mockResolvedValue(version("labv_1", { title: "Dune Strider", profile: { ...profile, name: "Dune Strider" }, card: { ...ready, profile: { ...profile, name: "Dune Strider" } } }));
    const id = addCardNode(v1);
    renderNode(id);
    await userEvent.click(await screen.findByRole("button", { name: "Scalesteed. Open card" }));
    await screen.findByRole("dialog", { name: "Scalesteed, animal card" });
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    const heading = screen.getByRole("heading", { name: "Scalesteed" });
    expect(heading).toHaveAttribute("contenteditable", "true");
    heading.textContent = "Dune Strider";
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await vi.waitFor(() => expect(editProfile).toHaveBeenCalled());
    expect(editProfile.mock.calls[0]![0]).toBe("labv_1");
    expect(editProfile.mock.calls[0]![1]).toMatchObject({ name: "Dune Strider", length: "3 m", habitat: "Dry savanna" });
    await vi.waitFor(() => expect((useGraph.getState().nodes.find((n) => n.id === v1)?.data as VersionData).version?.title).toBe("Dune Strider"));
  });

  it("a saved card is not asked for again on reload, and there is no way to make a second one", async () => {
    const v1 = withV1();
    const make = vi.spyOn(labApi, "card").mockResolvedValue(ready);
    const id = addCardNode(v1);
    useGraph.getState().updateNodeData<CardData>(id, (d) => ({ ...d, card: ready, versionId: "labv_1", autoStart: false }));
    renderNode(id);
    await settle(10);
    expect(make).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: /Make the card|Try again/ })).toBeNull();
  });

  it("a failed card can be tried again", async () => {
    const v1 = withV1();
    vi.spyOn(labApi, "card").mockResolvedValueOnce({ status: "failed", profile: null, angles: [], error: "The card could not be made. Try again." }).mockResolvedValue(ready);
    const id = addCardNode(v1);
    renderNode(id);
    await vi.waitFor(() => expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("button", { name: "Scalesteed. Open card" })).toBeInTheDocument();
  });

  it("an image can be animal A of a new Fusion, which sends its version id", async () => {
    const v1 = withV1();
    const f2 = addFusionFrom(v1);
    expect(useGraph.getState().edges.some((e) => e.source === v1 && e.target === f2 && e.targetPort === "a")).toBe(true);
    useGraph.getState().updateNodeData<FusionData>(f2, (d) => ({ ...d, names: { a: "", b: "eagle" } }));
    useGraph.getState().updateNodeConfig<FusionConfig>(f2, (c) => ({ ...c, style: "comic" }));
    renderNode(f2);
    expect(screen.getByText("lion × eagle")).toBeInTheDocument();
    expect(screen.getByText("earlier creature")).toBeInTheDocument();
    const start = vi.spyOn(mockTransport, "startRun");
    await startFusion(f2);
    expect(start).toHaveBeenCalledWith({ mode: "realistic", style: "comic", sireVersionId: "labv_1", damName: "eagle" });
  });

  it("a Fusion fed by an unfinished image waits for it", () => {
    useGraph.getState().addNode({ id: "f", type: "fusion", version: 3, position: { x: 0, y: 0 }, config: { mode: "realistic" }, data: { activeRunId: null, runIds: [] } });
    const pending = addVersionNode("f", { version: null, runId: "run_x", error: null });
    const f2 = addFusionFrom(pending);
    useGraph.getState().updateNodeData<FusionData>(f2, (d) => ({ ...d, names: { a: "", b: "eagle" } }));
    renderNode(f2);
    expect(screen.getByRole("button", { name: "Make creature" })).toBeDisabled();
    expect(screen.getByText("Wait for the connected image to finish.")).toBeInTheDocument();
  });
});
