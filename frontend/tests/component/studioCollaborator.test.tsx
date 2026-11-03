import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StudioCollaborator } from "../../src/screens/StudioCollaborator";

const api = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../src/api/client", () => ({ request: api.request, baseHeaders: (extra = {}) => extra }));

beforeEach(() => { localStorage.clear(); api.request.mockReset(); });

describe("creative collaborator", () => {
  it("shows and saves an inspection without generating a revision", async () => {
    const user = userEvent.setup(), onInspected = vi.fn(), onRevise = vi.fn();
    const review = { observation: "A spider face appears at the join.", suggestions: "Consider removing it." };
    api.request.mockResolvedValue({ data: { message: "The extra face may differ from your brief.", review,
      action: null, steps: [{ tool: "inspect_draft", reason: "You asked me to inspect it." }] } });
    const props = { versionId: "studio_a", hasReview: false, disabled: false, onReview: vi.fn(), onRevise, onInspected, onBusyChange: vi.fn() };
    const view = render(<StudioCollaborator {...props} />);
    await user.type(screen.getByLabelText("Your message"), "Inspect this image");
    await user.click(screen.getByRole("button", { name: "Ask collaborator" }));
    expect(await screen.findByText(/Inspected the selected draft/)).toHaveTextContent("extra face may differ");
    expect(onInspected).toHaveBeenCalledWith(review);
    expect(onRevise).not.toHaveBeenCalled();
    expect(api.request).toHaveBeenCalledWith("/evo/studio/versions/studio_a/collaborate", expect.objectContaining({ method: "POST" }));
    view.unmount();
    render(<StudioCollaborator {...props} />);
    expect(screen.getByText(/Inspect this image/)).toBeInTheDocument();
    expect(screen.getByText(/Inspected the selected draft/)).toBeInTheDocument();
  });

  it("lets the creator change a proposed action before running it", async () => {
    const user = userEvent.setup(), onRevise = vi.fn();
    api.request.mockResolvedValue({ data: { message: "Try this.", action: { type: "revise", reason: "Your direction", instruction: "Longer legs" }, steps: [] } });
    render(<StudioCollaborator versionId="studio_b" hasReview disabled={false} onReview={vi.fn()} onRevise={onRevise} onInspected={vi.fn()} onBusyChange={vi.fn()} />);
    await user.type(screen.getByLabelText("Your message"), "Change the legs");
    await user.click(screen.getByRole("button", { name: "Ask collaborator" }));
    const instruction = await screen.findByLabelText("Revision instruction");
    expect(onRevise).not.toHaveBeenCalled();
    await user.clear(instruction); await user.type(instruction, "More delicate legs");
    await user.click(screen.getByRole("button", { name: "Run this revision" }));
    expect(onRevise).toHaveBeenCalledWith("More delicate legs");
    await waitFor(() => expect(screen.queryByLabelText("Revision instruction")).not.toBeInTheDocument());
  });

  it("keeps a late reply with its original draft without applying the review to another view", async () => {
    const user = userEvent.setup(), onInspected = vi.fn(), onBusyChange = vi.fn();
    let finish!: (value: unknown) => void;
    api.request.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    const props = { versionId: "studio_original", hasReview: false, disabled: false, onReview: vi.fn(), onRevise: vi.fn(), onInspected, onBusyChange };
    const view = render(<StudioCollaborator {...props} />);
    await user.type(screen.getByLabelText("Your message"), "Inspect it");
    await user.click(screen.getByRole("button", { name: "Ask collaborator" }));
    expect(onBusyChange).toHaveBeenCalledWith(true);
    view.unmount();
    expect(onBusyChange).toHaveBeenLastCalledWith(false);
    finish({ data: { message: "The old draft has a second face.", action: null, review: { observation: "Second face", suggestions: "Remove it" }, steps: [] } });
    await waitFor(() => expect(localStorage.getItem("chimera.studio.chat.studio_original")).toContain("The old draft has a second face."));
    expect(onInspected).not.toHaveBeenCalled();
    render(<StudioCollaborator {...props} />);
    expect(screen.getByText(/The old draft has a second face/)).toBeInTheDocument();
  });
});
