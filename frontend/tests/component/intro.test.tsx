import { act, fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { parseRoute } from "../../src/app/route";
import { setTestSession } from "../../src/auth/auth";
import { hasSeenIntro, Intro } from "../../src/intro/Intro";
import { labApi } from "../../src/lab/api";
import { useWorkspaces } from "../../src/persistence/workspaces";
import { HomePage } from "../../src/screens/HomePage";
import { TUTORIAL_WS } from "../../src/tutorial/sandbox";
import { hasToured, useTour } from "../../src/tutorial/tourStore";
import { renderInFlow } from "./render";

beforeEach(() => {
  localStorage.clear();
  setTestSession({ id: "user-1" });
  useTour.setState({ active: false, phase: "lab" });
  window.history.replaceState(null, "", "/");
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("the welcome intro", () => {
  it("animates, then offers the tutorial or the workspaces; a key skips the animation", async () => {
    vi.useFakeTimers();
    const onClose = vi.fn();
    renderInFlow(<Intro onClose={onClose} />);
    expect(screen.getByRole("heading", { name: "Chimera Lab" })).toBeInTheDocument();
    expect(screen.getByText("Two animals in. One chimera out.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Take the tutorial" })).toBeDisabled(); // still animating
    fireEvent.keyDown(window, { key: " " });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });
    expect(screen.getByRole("button", { name: "Take the tutorial" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Skip to workspaces" })).toBeEnabled();
  });

  it("Skip to workspaces: the workspace list, and neither the intro nor the tutorial comes back", async () => {
    vi.useFakeTimers();
    const onClose = vi.fn();
    renderInFlow(<Intro onClose={onClose} />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    fireEvent.click(screen.getByRole("button", { name: "Skip to workspaces" }));
    expect(onClose).toHaveBeenCalled();
    expect(hasSeenIntro()).toBe(true);
    expect(hasToured()).toBe(true);
    expect(parseRoute(window.location.search)).toEqual({ view: "home" });
  });

  it("Take the tutorial: starts it in the tutorial workspace", async () => {
    vi.useFakeTimers();
    useWorkspaces.setState({ userId: "user-1", list: [], currentId: "main", loaded: true });
    renderInFlow(<Intro onClose={() => undefined} />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Take the tutorial" }));
      await vi.advanceTimersByTimeAsync(10);
    });
    expect(useTour.getState().active).toBe(true);
    expect(useWorkspaces.getState().currentId).toBe(TUTORIAL_WS);
  });
});

describe("the tutorial's last step", () => {
  it("opens the visitor's empty workspace instead of making a second one", async () => {
    const create = vi.spyOn(labApi, "createWorkspace");
    vi.spyOn(labApi, "workspaces").mockResolvedValue([{ id: "main", name: "My workspace", createdAt: "", updatedAt: "", imageCount: 0 }]);
    useWorkspaces.setState({ userId: "user-1", list: [{ id: "main", name: "My workspace", createdAt: "", updatedAt: "", imageCount: 0 }], currentId: null, loaded: true });
    useTour.setState({ active: true, phase: "workspaces" });
    renderInFlow(<HomePage />);
    fireEvent.click(screen.getByRole("button", { name: "New workspace" }));
    await vi.waitFor(() => expect(useWorkspaces.getState().currentId).toBe("main"));
    expect(create).not.toHaveBeenCalled();
    expect(useTour.getState().active).toBe(false);
  });
});
