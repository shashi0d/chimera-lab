import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { setTestSession, useAuth } from "../../src/auth/auth";
import { setTransport } from "../../src/evo/index";
import type { Publication } from "../../src/evo/types";
import { useGraph } from "../../src/graph/store";
import { labApi, type LabJob, type LabVersion } from "../../src/lab/api";
import { addEditNode, addVersionNode, lineage, versionNumber } from "../../src/lab/graph";
import { followJobs, generateEdit, stopFollowingJobs, useLab } from "../../src/lab/store";
import { ToolsPanel } from "../../src/lab/ToolsPanel";
import type { EditData } from "../../src/nodes/edit/types";
import type { VersionData } from "../../src/nodes/version/types";
import { CreationPage } from "../../src/screens/CreationPage";
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
  it("shows the path, and publishing puts the version in the gallery", async () => {
    const v1 = withV1();
    const edit = addEditNode(v1, "revise", "Blue fur");
    const v2 = addVersionNode(edit, { version: version("labv_2", { parentId: "labv_1", operation: "revise", instruction: "Blue fur" }), runId: null, error: null });
    vi.spyOn(labApi, "savedReview").mockResolvedValue(null);
    const publish = vi.spyOn(labApi, "publish").mockResolvedValue(version("labv_2", { parentId: "labv_1", operation: "revise", instruction: "Blue fur", publicationId: "pub_labv_2" }));
    renderInFlow(<ToolsPanel nodeId={v2} />);
    const path = screen.getByRole("list");
    expect(within(path).getAllByRole("listitem")).toHaveLength(2);
    expect(within(path).getByText("V2 · Revise")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Publish to the gallery" }));
    expect(publish).toHaveBeenCalledWith("labv_2", "lion × eagle");
    await vi.waitFor(() => expect(screen.getByRole("link", { name: "View in the gallery" })).toHaveAttribute("href", "/?creation=pub_labv_2"));
    expect((useGraph.getState().nodes.find((n) => n.id === v2)?.data as VersionData).version?.publicationId).toBe("pub_labv_2");
    expect(await screen.findByText(/19 of 20 lab actions left today/)).toBeInTheDocument();
  });

  it("a collaborator's suggestion becomes a Revise card the user can edit before running", async () => {
    const v1 = withV1();
    vi.spyOn(labApi, "savedReview").mockResolvedValue(null);
    vi.spyOn(labApi, "collaborate").mockResolvedValue({ message: "Try this.", action: { type: "revise", instruction: "Remove the extra face", reason: "Mismatch" }, review: null, steps: [] });
    const revise = vi.spyOn(labApi, "revise");
    renderInFlow(<ToolsPanel nodeId={v1} />);
    await userEvent.type(screen.getByLabelText("Message the collaborator"), "Anything off?");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    await userEvent.click(await screen.findByRole("button", { name: "Add as a Revise card" }));
    const edit = nodesOf("edit")[0]!;
    expect(edit.config).toEqual({ operation: "revise", instruction: "Remove the extra face" });
    expect(revise).not.toHaveBeenCalled();
  });
});

describe("sign-in", () => {
  it("the Lab asks to sign in; the gallery doesn't", () => {
    setTestSession(null);
    renderInFlow(<LabView ready runId={null} />);
    expect(screen.getByRole("heading", { name: "Sign in to create" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Email me a sign-in link" })).toBeDisabled();
    expect(screen.getByRole("link", { name: "browse the gallery" })).toHaveAttribute("href", "/");
  });

  it("explains when sign-in is not configured", () => {
    useAuth.setState({ status: "unavailable", error: "Sign-in is not configured on this server." });
    renderInFlow(<LabView ready runId={null} />);
    expect(screen.getByRole("alert")).toHaveTextContent("not configured");
  });
});

describe("a published creation in the gallery", () => {
  it("shows the final image and every step from the animals", async () => {
    const pub: Publication = {
      publicationId: "pub_labv_3", title: "Fox-lion", createdAt: "2026-11-03T00:00:00Z", mode: "realistic", imageUrl: "/evo/files/lab/labv_3.png", sourceCreatureId: "crt_1",
      sire: { commonName: "lion", scientificName: "Panthera leo", source: "name", confidence: null }, dam: { commonName: "red fox", scientificName: null, source: "name", confidence: null },
      steps: [
        { versionId: "labv_1", operation: "fusion", instruction: "lion × red fox (realistic)", imageUrl: "/a.png", createdAt: "" },
        { versionId: "labv_2", operation: "revise", instruction: "Longer legs", imageUrl: "/b.png", createdAt: "" },
        { versionId: "labv_3", operation: "paint", instruction: "Blue mane", imageUrl: "/c.png", createdAt: "" },
      ],
    };
    vi.spyOn(mockTransport, "getPublication").mockResolvedValue(pub);
    renderInFlow(<CreationPage publicationId="pub_labv_3" />);
    expect(await screen.findByRole("heading", { name: "Fox-lion" })).toBeInTheDocument();
    expect(screen.getByText("2 edits after the agent's image")).toBeInTheDocument();
    const steps = screen.getAllByRole("listitem").map((li) => li.textContent);
    expect(steps).toEqual(["Animals: lion and red fox", "V1 · Fusion: the agent's image", "V2 · Revise: Longer legs", "V3 · Paint: Blue mane"]);
    expect(screen.getByRole("link", { name: "How the agent made V1" })).toHaveAttribute("href", "/?creature=crt_1");
  });

  it("an unpublished creation says it isn't in the gallery", async () => {
    renderInFlow(<CreationPage publicationId="pub_gone" />);
    expect(await screen.findByRole("button", { name: "Back to the gallery" })).toBeInTheDocument();
  });
});
