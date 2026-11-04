import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { useConnectivity } from "../../src/connectivity/store";
import { useLimits } from "../../src/evo/data";
import { setTransport } from "../../src/evo/index";
import { mockConfig, mockTransport, resetMock, runEvents } from "../fakes/evoTransport";
import { stopAllStreams, useEvoRuns, type RunRecord } from "../../src/evo/runs";
import type { AgentEvent, Parent } from "../../src/evo/types";
import { useGraph } from "../../src/graph/store";
import { useFusionStart } from "../../src/nodes/fusion/start";
import { renderNode } from "./render";

beforeEach(() => {
  resetMock();
  mockConfig.latencyMs = 0;
  setTransport(mockTransport);
  useLimits.setState({ status: "idle", data: null, error: null, capError: null });
  useEvoRuns.setState({ runs: {} });
  useGraph.getState().reset();
  useFusionStart.setState({ starting: {}, errors: {}, identify: null });
  useConnectivity.setState({ browserOnline: true, serverReachable: true, forced: null, status: "online" });
  return () => stopAllStreams();
});

const lion: Parent = { commonName: "lion", scientificName: null, source: "name", confidence: null };
const eagle: Parent = { commonName: "golden eagle", scientificName: null, source: "name", confidence: null };

/** Put a run in the store as if the stream had delivered these events. */
function putRun(runId: string, events: AgentEvent[], over: Partial<RunRecord> = {}) {
  const rec: RunRecord = { runId, snapshot: null, accepted: null, events, stream: "closed", loadError: null, ...over };
  useEvoRuns.setState((s) => ({ runs: { ...s.runs, [runId]: rec } }));
}

describe("Fusion node", () => {
  const seedFusion = (data: Record<string, unknown> = {}) =>
    useGraph.getState().load({
      schemaVersion: 1,
      graphId: "g",
      nodes: [{ id: "f", type: "fusion", version: 3, position: { x: 0, y: 0 }, config: { style: "real" }, data: { activeRunId: null, runIds: [], names: { a: "", b: "" }, ...data } }],
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
    expect(within(group).getAllByRole("radio").map((r) => r.textContent)).toEqual(["Real", "Sketch", "Anime", "Comic", "Cartoon"]);
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
    expect(screen.getByText(/Today's Fusion runs are used up/)).toBeInTheDocument();
  });

  it("a refusal shows what to change", () => {
    seedFusion({ names: { a: "lion", b: "golden eagle" } });
    useFusionStart.setState({ errors: { f: { code: "HUMAN_DETECTED", message: "x", retryable: false } } });
    renderNode("f");
    expect(screen.getByRole("alert")).toHaveTextContent("This looks like a photo of a person.");
    expect(screen.getByRole("alert")).toHaveTextContent("Chimera Lab only uses animal photos.");
  });

  it("while a run is queued, the node shows its place and that it is generating", () => {
    putRun("q", runEvents("queued", "q", lion, eagle).slice(0, 1), { stream: "open" });
    seedFusion({ activeRunId: "q", runIds: ["q"], names: { a: "lion", b: "golden eagle" } });
    renderNode("f");
    expect(screen.getByText("Queued · #2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generating…" })).toBeDisabled();
  });
});
