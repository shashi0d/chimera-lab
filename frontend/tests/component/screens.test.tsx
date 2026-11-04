import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiRequestError } from "../../src/api/errors";
import { useConnectivity } from "../../src/connectivity/store";
import { useCreatures, useGallery, useLimits } from "../../src/evo/data";
import { setTransport } from "../../src/evo/index";
import { mockConfig, mockTransport, resetMock } from "../fakes/evoTransport";
import { stopAllStreams, useEvoRuns, type RunRecord } from "../../src/evo/runs";
import type { AgentEvent } from "../../src/evo/types";
import { useGraph } from "../../src/graph/store";
import { useFusionStart } from "../../src/nodes/fusion/start";
import { TracePanel } from "../../src/trace/TracePanel";
import { renderNode } from "./render";
import success from "../../../docs/api_fixtures/run_success.json";
import hostTie from "../../../docs/api_fixtures/run_host_tie.json";
import queued from "../../../docs/api_fixtures/run_queued.json";
import runError from "../../../docs/api_fixtures/run_error.json";
import cap from "../../../docs/api_fixtures/run_cap.json";

beforeEach(() => {
  resetMock();
  mockConfig.latencyMs = 0;
  mockConfig.scenario = "success";
  mockConfig.holdAt = null;
  setTransport(mockTransport);
  useGallery.setState({ status: "idle", data: null, error: null, nextCursor: null });
  useCreatures.setState({ byId: {} });
  useLimits.setState({ status: "idle", data: null, error: null, capError: null });
  useEvoRuns.setState({ runs: {} });
  useGraph.getState().reset();
  useFusionStart.setState({ starting: {}, errors: {}, identify: null });
  useConnectivity.setState({ browserOnline: true, serverReachable: true, forced: null, status: "online" });
  return () => stopAllStreams();
});

/** Put a run in the store as if the stream had delivered these events, and keep the panel from opening a stream. */
function putRun(runId: string, events: AgentEvent[], over: Partial<RunRecord> = {}) {
  const rec: RunRecord = { runId, snapshot: null, accepted: null, events, stream: "closed", loadError: null, choice: { sending: false, error: null, sent: null }, ...over };
  useEvoRuns.setState((s) => ({ runs: { ...s.runs, [runId]: rec } }));
}
const evs = (f: { events: unknown[] }) => f.events as AgentEvent[];
/** The host-tie events up to the open question, with its expiry moved two minutes past now. */
/** Keep a mounted panel on the events given: the snapshot says "waiting" and the stream sends nothing new. */
function holdServer(runId: string) {
  vi.spyOn(mockTransport, "getRun").mockResolvedValue({ runId, status: "needs_choice", lastEventId: 5 } as never);
  vi.spyOn(mockTransport, "streamEvents").mockReturnValue({ stop: () => undefined });
}
function tieUpToQuestion(): AgentEvent[] {
  const all = evs(hostTie);
  return all.slice(0, all.findIndex((e) => e.type === "needs_choice") + 1).map((e) => (e.type === "needs_choice" ? { ...e, expiresAt: new Date(Date.now() + 120_000).toISOString() } : e));
}

describe("live trace panel", () => {
  it("queued: the position, runs ahead and the 5-minute expectation", () => {
    putRun("q", evs(queued).slice(0, 1), { stream: "open" });
    render(<TracePanel runId="q" />);
    expect(screen.getByText("Position 2 in the queue")).toBeInTheDocument();
    expect(screen.getByText(/2 runs ahead of yours/)).toBeInTheDocument();
    expect(screen.getAllByText(/about a minute/).length).toBeGreaterThan(0);
  });

  it("running: every step with the agent's reason in plain words, images labelled Generated fusion", () => {
    putRun("s", evs(success).slice(0, 10), { stream: "open" });
    render(<TracePanel runId="s" />);
    const log = screen.getByRole("log", { name: "Agent steps" });
    expect(within(log).getAllByText("Looked up an animal", { exact: false })).toHaveLength(2);
    expect(within(log).getByText("Chose a body plan", { exact: false })).toBeTruthy();
    expect(within(log).getByText(/Chosen horse as host for realistic mode/)).toBeInTheDocument();
    expect(within(log).getByText("Generated fusion")).toBeInTheDocument();
    expect(within(log).getByText("4 checks failed")).toBeInTheDocument();
    expect(screen.getByText("Running")).toBeInTheDocument();
  });

  it("needs_choice: the question with both options; answering posts the choice", async () => {
    putRun("t", tieUpToQuestion(), { stream: "open" });
    holdServer("t");
    const post = vi.spyOn(mockTransport, "postChoice").mockResolvedValue();
    render(<TracePanel runId="t" />);
    expect(screen.getByRole("heading", { name: "Both animals can carry the body. Which should be the host?" })).toBeInTheDocument();
    expect(screen.getByText(/the agent decides itself and says why/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "domestic goat" }));
    expect(post).toHaveBeenCalledWith("t", "choice_fx_1", "domestic goat");
    expect(await screen.findByText(/You chose domestic goat/)).toBeInTheDocument();
  });

  it("a late answer (409) says the agent decided itself", async () => {
    putRun("t2", tieUpToQuestion(), { stream: "open" });
    holdServer("t2");
    render(<TracePanel runId="t2" />);
    vi.spyOn(mockTransport, "postChoice").mockRejectedValue(new ApiRequestError({ code: "VALIDATION_FAILED", message: "", retryable: false }, 409));
    await userEvent.click(screen.getByRole("button", { name: "tortoise" }));
    expect(await screen.findByText(/already answered or has expired/)).toBeInTheDocument();
  });

  it("cap_reached is shown as a notice while the run goes on", () => {
    const all = evs(cap);
    putRun("c", all.slice(0, all.findIndex((e) => e.type === "cap_reached") + 1), { stream: "open" });
    render(<TracePanel runId="c" />);
    expect(screen.getByText("This run has used its 4 renders. The agent now finalizes its best image.")).toBeInTheDocument();
    expect(screen.getByText("Running")).toBeInTheDocument();
  });

  it("finished: the creature leads, with host, Can it live and the way to the card", async () => {
    putRun("done", evs(success));
    render(<TracePanel runId="done" />);
    expect(await screen.findByText("Host: horse.")).toBeInTheDocument();
    expect(screen.getByText("Generated fusion", { selector: ".pill" })).toBeTruthy();
    expect(screen.getByText(/How the agent made it \(10 steps\)/)).toBeInTheDocument();
  });

  it("error: what happened in plain words, no raw upstream text", () => {
    putRun("e", evs(runError));
    render(<TracePanel runId="e" />);
    expect(screen.getByText("The image model stopped answering, so this run ended.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Make a new creature" })).toBeInTheDocument();
  });

  it("an unknown run id says it can't be found", async () => {
    render(<TracePanel runId="run_nope" />);
    expect(await screen.findByText("This run can't be found.")).toBeInTheDocument();
  });
});

describe("Fusion node (agent)", () => {
  const seedFusion = (data: Record<string, unknown> = {}) =>
    useGraph.getState().load({
      schemaVersion: 1,
      graphId: "g",
      nodes: [{ id: "f", type: "fusion", version: 3, position: { x: 0, y: 0 }, config: { mode: "realistic" }, data: { activeRunId: null, runIds: [], names: { a: "", b: "" }, ...data } }],
      edges: [],
    });

  it("without photos, two name fields; Make creature waits for both, with the reason shown", async () => {
    seedFusion();
    renderNode("f");
    const make = screen.getByRole("button", { name: "Make creature" });
    expect(make).toBeDisabled();
    expect(screen.getByText("Add a photo or type a name for both animals.")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Animal A"), "lion");
    await userEvent.type(screen.getByLabelText("Animal B"), "golden eagle");
    await waitFor(() => expect(screen.getByRole("button", { name: "Make creature" })).toBeEnabled());
  });

  it("five art styles as a radio group; the hint describes the style", async () => {
    seedFusion({ names: { a: "lion", b: "golden eagle" } });
    renderNode("f");
    const group = screen.getByRole("radiogroup", { name: "Art style" });
    expect(within(group).getAllByRole("radio").map((r) => r.textContent)).toEqual(["Real", "Drawing", "Anime", "Comic", "Cartoon"]);
    await userEvent.click(within(group).getByRole("radio", { name: "Anime" }));
    expect(useGraph.getState().nodes[0]?.config).toMatchObject({ style: "anime" });
    expect(screen.getByText(/anime line art/)).toBeInTheDocument();
  });

  it("capped: Make creature is disabled and says why", async () => {
    mockConfig.scenario = "limits_capped";
    await act(() => useLimits.getState().refresh());
    seedFusion({ names: { a: "lion", b: "golden eagle" } });
    renderNode("f");
    expect(screen.getByRole("button", { name: "Make creature" })).toBeDisabled();
    expect(screen.getByText(/Today's live runs are used up/)).toBeInTheDocument();
  });

  it("a refusal shows what to change", () => {
    seedFusion({ names: { a: "lion", b: "golden eagle" } });
    useFusionStart.setState({ errors: { f: { code: "HUMAN_DETECTED", message: "x", retryable: false } } });
    renderNode("f");
    expect(screen.getByRole("alert")).toHaveTextContent("This looks like a photo of a person.");
    expect(screen.getByRole("alert")).toHaveTextContent("Chimera Lab only uses animal photos.");
  });

  it("while a run is queued, the node shows its place and that it is generating", () => {
    putRun("q", evs(queued).slice(0, 1), { stream: "open" });
    seedFusion({ activeRunId: "q", runIds: ["q"], names: { a: "lion", b: "golden eagle" } });
    renderNode("f");
    expect(screen.getByText("Queued · #2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generating…" })).toBeDisabled();
  });
});
