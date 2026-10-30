import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../src/api/client";
import { useConnectivity } from "../../src/connectivity/store";
import { useGraph } from "../../src/graph/store";
import { useRuns } from "../../src/runs/store";
import type { Run } from "../../src/types/api";
import { edge, fusion, img, seed } from "../unit/helpers";
import { renderNode } from "./render";

const steps = (current: number, status: "running" | "failed" = "running") =>
  ["load_inputs", "identify", "match", "hybrid_check", "rules_check", "compile", "generate", "store"].map((key, i) => ({
    key,
    label: key,
    status: i < current ? ("succeeded" as const) : i === current ? status : ("pending" as const),
    startedAt: i <= current ? new Date(Date.now() - 1000).toISOString() : null,
    endedAt: i < current ? new Date().toISOString() : null,
    detail: null,
    calls: null,
    tokens: null,
  }));

function makeRun(over: Partial<Run>): Run {
  return {
    id: "run1", graphId: "g", nodeId: "f", sessionId: null, status: "running", steps: steps(1), result: null, error: null,
    failedInput: null, createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(), version: 1, usage: {}, ...over,
  };
}

beforeEach(() => {
  useConnectivity.setState({ browserOnline: true, serverReachable: true, forced: null, status: "online" });
  useRuns.setState({ runs: {}, startErrors: {}, starting: {}, transport: { watch: () => ({ stop: () => undefined }) } });
  seed([img("a"), img("b"), fusion("f")], [edge("a", "f", "a"), edge("b", "f", "b")]);
});

describe("Fusion node (TASKSHEET 7.2, 7.3, 7.5)", () => {
  it("Fuse is disabled with a hint when an input is missing", () => {
    seed([img("a"), fusion("f")], [edge("a", "f", "a")]);
    renderNode("f");
    expect(screen.getByRole("button", { name: "Fuse" })).toBeDisabled();
    expect(screen.getByText("Connect one more image to fuse.")).toBeInTheDocument();
  });

  it("Fuse is disabled while offline, with a tooltip-style hint", () => {
    useConnectivity.getState().setBrowserOnline(false);
    renderNode("f");
    expect(screen.getByRole("button", { name: "Fuse" })).toBeDisabled();
    expect(screen.getByText(/You're offline/)).toBeInTheDocument();
  });

  it("starts a run once, even on double-click (idempotency + disabled button)", async () => {
    let resolve: (r: Run) => void = () => undefined;
    const spy = vi.spyOn(api, "startRun").mockImplementation(() => new Promise((r) => (resolve = r)));
    renderNode("f");
    const btn = screen.getByRole("button", { name: "Fuse" });
    await userEvent.dblClick(btn);
    expect(spy).toHaveBeenCalledTimes(1);
    const [body, key] = spy.mock.calls[0] as [{ nodeId: string }, string];
    expect(body.nodeId).toBe("f");
    expect(key).toMatch(/[0-9a-f-]{16,}/);
    await act(async () => resolve(makeRun({})));
    expect(useGraph.getState().nodes.find((n) => n.id === "f")?.data.activeRunId).toBe("run1");
  });

  it("shows the step list, elapsed time and a cancel button while running", () => {
    useRuns.getState().upsert(makeRun({ steps: steps(2) }));
    useGraph.getState().updateNodeData("f", (d) => ({ ...d, activeRunId: "run1" }));
    renderNode("f");
    expect(screen.getByText("2 of 8")).toBeInTheDocument();
    expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent("match");
    expect(screen.getByRole("button", { name: "Cancel" })).toBeEnabled();
    expect(screen.getByLabelText(/Elapsed/)).toBeInTheDocument();
  });

  it("long waits: message after 20s, prominent cancel after 120s", () => {
    useRuns.getState().upsert(makeRun({ createdAt: new Date(Date.now() - 25_000).toISOString() }));
    useGraph.getState().updateNodeData("f", (d) => ({ ...d, activeRunId: "run1" }));
    const { unmount } = renderNode("f");
    expect(screen.getByText(/can take up to 2 minutes/)).toBeInTheDocument();
    unmount();
    useRuns.getState().upsert(makeRun({ version: 2, createdAt: new Date(Date.now() - 130_000).toISOString() }));
    renderNode("f");
    expect(screen.getByText(/longer than usual/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveClass("btn--danger");
  });

  it("retryable failure: explains and offers Retry fusion", () => {
    useRuns.getState().upsert(makeRun({ status: "failed", steps: steps(6, "failed"), error: { code: "UPSTREAM_ERROR", message: "raw upstream text", retryable: true, retryAfterMs: null, details: {}, errorId: null } }));
    useGraph.getState().updateNodeData("f", (d) => ({ ...d, activeRunId: "run1" }));
    renderNode("f");
    expect(screen.getByRole("alert")).toHaveTextContent("The model service had a problem.");
    expect(screen.queryByText("raw upstream text")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry fusion" })).toBeEnabled();
  });

  it("BUDGET_EXCEEDED: clear message, no retry", () => {
    useRuns.getState().upsert(makeRun({ status: "failed", error: { code: "BUDGET_EXCEEDED", message: "", retryable: false, retryAfterMs: null, details: {}, errorId: null } }));
    useGraph.getState().updateNodeData("f", (d) => ({ ...d, activeRunId: "run1" }));
    renderNode("f");
    expect(screen.getByRole("alert")).toHaveTextContent("budget is used up");
    expect(screen.queryByRole("button", { name: "Retry fusion" })).not.toBeInTheDocument();
  });

  it("RATE_LIMITED: counts down using retryAfterMs, then retries automatically", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const start = vi.spyOn(api, "startRun").mockResolvedValue(makeRun({ id: "run2" }));
    useRuns.getState().upsert(makeRun({ status: "failed", error: { code: "RATE_LIMITED", message: "", retryable: true, retryAfterMs: 3000, details: {}, errorId: null } }));
    useGraph.getState().updateNodeData("f", (d) => ({ ...d, activeRunId: "run1" }));
    renderNode("f");
    expect(screen.getByText(/Retrying in 3s/)).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3500);
    });
    expect(start).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });

  it("unknown errors show an error id the user can report", () => {
    useRuns.getState().upsert(makeRun({ status: "failed", error: { code: "INTERNAL", message: "", retryable: true, retryAfterMs: null, details: {}, errorId: "e1d2c3" } }));
    useGraph.getState().updateNodeData("f", (d) => ({ ...d, activeRunId: "run1" }));
    renderNode("f");
    expect(screen.getByText(/error id e1d2c3/)).toBeInTheDocument();
  });

  it("interrupted runs offer a re-run", () => {
    useRuns.getState().upsert(makeRun({ status: "interrupted", error: { code: "RUN_INTERRUPTED", message: "", retryable: true, retryAfterMs: null, details: {}, errorId: null } }));
    useGraph.getState().updateNodeData("f", (d) => ({ ...d, activeRunId: "run1" }));
    renderNode("f");
    expect(screen.getByText(/server restarted/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry fusion" })).toBeEnabled();
  });

  it("keyboard users can connect inputs with the slot selects", async () => {
    seed([img("a"), img("b"), fusion("f")]);
    renderNode("f");
    await userEvent.selectOptions(screen.getByLabelText("Connect image A"), "a");
    await userEvent.selectOptions(screen.getByLabelText("Connect image B"), "b");
    expect(useGraph.getState().edges.map((e) => `${e.source}->${e.targetPort}`)).toEqual(["a->a", "b->b"]);
    expect(screen.getByRole("button", { name: "Fuse" })).toBeEnabled();
  });
});
