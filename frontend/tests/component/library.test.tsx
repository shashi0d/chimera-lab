import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { setTestSession } from "../../src/auth/auth";
import { LibraryDialog } from "../../src/canvas/LibraryDialog";
import { setTransport } from "../../src/evo/index";
import { useGraph } from "../../src/graph/store";
import { labApi, type LabJob, type LabVersion, type WorkspaceInfo } from "../../src/lab/api";
import { confirmImageDelete, deleteNodes } from "../../src/lab/deletion";
import { addEditNode, addVersionNode } from "../../src/lab/graph";
import { generateEdit, stopFollowingJobs, useLab } from "../../src/lab/store";
import { sketchKey, type EditData } from "../../src/nodes/edit/types";
import { getBlob, putBlob } from "../../src/persistence/blobStore";
import { useWorkspaces } from "../../src/persistence/workspaces";
import { ChimerasPage } from "../../src/screens/ChimerasPage";
import { HomePage } from "../../src/screens/HomePage";
import { ConfirmDialog } from "../../src/ui/ConfirmDialog";
import { mockTransport, resetMock } from "../fakes/evoTransport";
import { renderNode } from "./render";

const version = (id: string, over: Partial<LabVersion> = {}): LabVersion => ({
  id, parentId: null, runId: "run_1", creatureId: "crt_1", operation: "fusion", instruction: "lion × eagle",
  imageUrl: `/evo/files/lab/${id}.png`, createdAt: "2026-11-04T00:00:00Z", isFinal: false, publicationId: null, title: "Sky Lion", ...over,
});
const ws = (id: string, name: string, imageCount = 0): WorkspaceInfo => ({ id, name, imageCount, createdAt: "2026-11-04T00:00:00Z", updatedAt: "2026-11-04T00:00:00Z" });

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
  useWorkspaces.setState({ userId: "user-1", list: [ws("main", "My workspace", 2), ws("ws_b", "Reef", 1)], currentId: "main", loaded: true });
});

describe("deleting images", () => {
  it("asks first; confirming deletes the image on the server and clears undo", async () => {
    const v1 = withV1();
    const del = vi.spyOn(labApi, "deleteVersion").mockResolvedValue();
    render(<ConfirmDialog />);
    const done = deleteNodes([v1]);
    const dialog = await screen.findByRole("alertdialog", { name: "Delete this image?" });
    expect(within(dialog).getByText(/removed from your library and the server/)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete image" }));
    await done;
    expect(del).toHaveBeenCalledWith("labv_1");
    expect(useGraph.getState().nodes.some((n) => n.id === v1)).toBe(false);
    expect(useGraph.getState().past).toHaveLength(0);
  });

  it("cancelling keeps the image", async () => {
    const v1 = withV1();
    const del = vi.spyOn(labApi, "deleteVersion").mockResolvedValue();
    render(<ConfirmDialog />);
    const answer = confirmImageDelete([v1]);
    await userEvent.click(await screen.findByRole("button", { name: "Cancel" }));
    expect(await answer).toBe(false);
    expect(del).not.toHaveBeenCalled();
  });

  it("cards without images are removed without a question", async () => {
    withV1();
    expect(await confirmImageDelete(["f"])).toBe(true);
  });
});

describe("drawing on a creature", () => {
  it("a Draw edit needs a drawing, then sends it with the optional note", async () => {
    const v1 = withV1();
    const edit = addEditNode(v1, "sketch", "");
    const view = renderNode(edit);
    expect(screen.getByRole("button", { name: "Generate" })).toBeDisabled();
    expect(screen.getByText("Draw on the image first.")).toBeInTheDocument();
    view.unmount();
    const drawing = new Blob(["png"], { type: "image/png" });
    await putBlob(sketchKey(edit), drawing);
    useGraph.getState().updateNodeData<EditData>(edit, (d) => ({ ...d, hasSketch: true }));
    const job: LabJob = { id: "labjob_s", operation: "sketch", status: "queued", stage: "Waiting", parentId: "labv_1", instruction: "", createdAt: "", updatedAt: "", result: null, error: null };
    const sketch = vi.spyOn(labApi, "sketch").mockResolvedValue(job);
    vi.spyOn(labApi, "jobs").mockResolvedValue([job]);
    await generateEdit(edit);
    expect(sketch).toHaveBeenCalledTimes(1);
    expect(sketch.mock.calls[0]![0]).toBe("labv_1");
    expect(sketch.mock.calls[0]![2]).toBe("");
    expect(await getBlob(sketchKey(edit))).toBeTruthy();
  });
});

describe("add image (the library)", () => {
  it("lists everything made so far, and adding one puts it on the canvas", async () => {
    vi.spyOn(labApi, "versions").mockResolvedValue([version("labv_1"), version("labv_2", { title: "Reef Fox" })]);
    const onAddVersion = vi.fn();
    render(<LibraryDialog onClose={() => undefined} onAddFiles={() => undefined} onAddVersion={onAddVersion} />);
    await userEvent.click(await screen.findByRole("button", { name: /Reef Fox/ }));
    expect(onAddVersion).toHaveBeenCalledWith(expect.objectContaining({ id: "labv_2" }));
    expect(screen.getByRole("button", { name: "Upload from device" })).toBeInTheDocument();
  });
});

describe("home page (workspaces)", () => {
  it("lists every workspace as a tile and opens one", async () => {
    vi.spyOn(labApi, "workspaces").mockResolvedValue([ws("main", "My workspace", 2), ws("ws_b", "Reef", 1)]);
    render(<HomePage />);
    expect(screen.getByText("New workspace", { selector: ".ws-tile__name" })).toBeInTheDocument();
    expect(screen.getByText(/2 images/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Open Reef" }));
    expect(useWorkspaces.getState().currentId).toBe("ws_b");
    expect(window.location.search).toBe("?ws=ws_b");
  });

  it("New workspace creates one and opens it", async () => {
    vi.spyOn(labApi, "workspaces").mockResolvedValue([ws("main", "My workspace")]);
    const create = vi.spyOn(labApi, "createWorkspace").mockResolvedValue(ws("ws_new", "Untitled workspace 3"));
    render(<HomePage />);
    await userEvent.click(screen.getByRole("button", { name: "New workspace" }));
    await vi.waitFor(() => expect(useWorkspaces.getState().currentId).toBe("ws_new"));
    expect(create).toHaveBeenCalledWith(expect.stringMatching(/^Untitled workspace \d+$/));
  });

  it("a workspace's images can be listed", async () => {
    vi.spyOn(labApi, "workspaceImages").mockResolvedValue([version("labv_9", { title: "Reef Fox" })]);
    render(<HomePage />);
    await userEvent.click(screen.getByRole("button", { name: "Images in Reef" }));
    expect(await screen.findByRole("img", { name: "Reef Fox" })).toBeInTheDocument();
  });

  it("deleting a workspace asks first and says its images go too", async () => {
    vi.spyOn(labApi, "workspaces").mockResolvedValue([ws("main", "My workspace", 2), ws("ws_b", "Reef", 1)]);
    const del = vi.spyOn(labApi, "deleteWorkspace").mockResolvedValue({ imagesDeleted: 1 });
    render(
      <>
        <HomePage />
        <ConfirmDialog />
      </>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Delete Reef" }));
    const dialog = await screen.findByRole("alertdialog", { name: 'Delete "Reef"?' });
    expect(within(dialog).getByText(/its 1 image/)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete workspace" }));
    await vi.waitFor(() => expect(del).toHaveBeenCalledWith("ws_b"));
    expect(useWorkspaces.getState().list.map((w) => w.id)).toEqual(["main"]);
  });
});

describe("chimeras page", () => {
  it("shows every saved creature as a card", async () => {
    vi.spyOn(labApi, "chimeras").mockResolvedValue([
      version("labv_1", { saved: true, card: { status: "running", profile: null, angles: [], error: null } }),
      version("labv_2", { saved: true, title: "Reef Fox" }),
    ]);
    render(<ChimerasPage />);
    const tile = await screen.findByRole("button", { name: "Sky Lion. Open card" });
    expect(screen.getByRole("button", { name: "Reef Fox. Open card" })).toBeInTheDocument();
    expect(within(tile).getByText("Drawing the card…")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Reef Fox. Open card" }));
    expect(await screen.findByRole("dialog", { name: "Reef Fox, animal card" })).toBeInTheDocument();
  });
});
