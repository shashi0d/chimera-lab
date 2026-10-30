import { ReactFlowProvider } from "@xyflow/react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppErrorBoundary } from "../../src/app/AppErrorBoundary";
import { Banners } from "../../src/app/Banners";
import { SidePanel } from "../../src/app/SidePanel";
import { NodeErrorBoundary } from "../../src/canvas/NodeErrorBoundary";
import { useConnectivity } from "../../src/connectivity/store";
import { useGraph } from "../../src/graph/store";
import { UnsupportedNodeView } from "../../src/nodes/unsupported/NodeView";
import { useUi } from "../../src/ui/uiStore";
import { result, seed } from "../unit/helpers";

function Boom(): never {
  throw new Error("boom");
}

beforeEach(() => {
  vi.spyOn(console, "error").mockImplementation(() => undefined);
  useConnectivity.setState({ browserOnline: true, serverReachable: true, forced: null, status: "online" });
});

describe("broken states (TASKSHEET 7.6)", () => {
  it("a crashing node renders a recoverable card", async () => {
    let crash = true;
    function Maybe() {
      if (crash) throw new Error("x");
      return <p>fine</p>;
    }
    render(
      <NodeErrorBoundary nodeId="n1">
        <Maybe />
      </NodeErrorBoundary>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("This node failed to render");
    crash = false;
    await userEvent.click(screen.getByRole("button", { name: "Reload node" }));
    expect(screen.getByText("fine")).toBeInTheDocument();
  });

  it("the app boundary offers a reload and an error id", () => {
    render(
      <AppErrorBoundary>
        <Boom />
      </AppErrorBoundary>,
    );
    expect(screen.getByRole("button", { name: "Reload app" })).toBeInTheDocument();
    expect(screen.getByText(/Your canvas is saved/)).toBeInTheDocument();
    expect(screen.getByText(/Error id/)).toBeInTheDocument();
  });

  it("unknown node types render a placeholder", () => {
    render(<UnsupportedNodeView type="style" catalog={3} />);
    expect(screen.getByText(/“style” node/)).toBeInTheDocument();
  });

  it("newer graph versions show a read-only banner", () => {
    useGraph.getState().load({ schemaVersion: 9, graphId: "g", nodes: [], edges: [] }, { readOnly: true });
    render(<Banners />);
    expect(screen.getByText(/read-only/)).toBeInTheDocument();
    useGraph.getState().reset();
  });
});

describe("connectivity banners (TASKSHEET 7.7)", () => {
  it("offline banner", () => {
    useConnectivity.getState().setBrowserOnline(false);
    render(<Banners />);
    expect(screen.getByText(/You're offline/)).toBeInTheDocument();
  });
  it("server unreachable banner is distinct and offers a manual retry", () => {
    useConnectivity.getState().setServerReachable(false);
    render(<Banners />);
    expect(screen.getByText(/server can't be reached/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try now" })).toBeInTheDocument();
  });
});

describe("How this was made panel (TASKSHEET 7.4)", () => {
  it("shows parents, hybrid facts, donors, notes and the prompt; Escape closes it", async () => {
    seed([
      result("r", {
        selected: 0,
        versions: [
          {
            runId: "run1", assetId: "a", creatureId: "c", imageUrl: "/x", createdAt: "",
            spec: {
              parents: [
                { slot: "A", assetId: "a", reading: { isAnimal: true, containsHuman: false, commonName: "Lion", scientificName: "Panthera leo", confidence: 0.94, visibleParts: ["mane"], bodyPlan: "quadruped", notes: "" }, match: { animalId: "lion", tier: 1, commonName: "Lion", scientificName: "Panthera leo", matchedOn: "scientific_name", facts: {} } },
                { slot: "B", assetId: "b", reading: { isAnimal: true, containsHuman: false, commonName: "Quokka", scientificName: null, confidence: 0.8, visibleParts: [], bodyPlan: "quadruped", notes: "" }, match: null },
              ],
              realHybrid: { hybridId: "liger", name: "Liger", facts: { fertility: "males sterile|females fertile" } },
              bodyPlan: "quadruped",
              partDonors: { head: "A", body: "B", limbs: "B", covering: "A", tail: "A" },
              rationale: "Because.",
              name: "Leokka",
              warnings: [{ ruleId: "R-S1-01", message: "Masses differ.", severity: "warning" }],
              prompt: "Reference image 1 shows a lion.",
              model: { vision: "mock-muse-spark", image: "mock-muse-image" },
            },
          },
        ],
      }),
    ]);
    useUi.getState().openPanel("r");
    render(
      <ReactFlowProvider>
        <SidePanel />
      </ReactFlowProvider>,
    );
    expect(screen.getByRole("heading", { name: "How this was made" })).toBeInTheDocument();
    expect(screen.getByText("Panthera leo", { selector: "i" })).toBeInTheDocument();
    expect(screen.getByText(/Not in field data/)).toBeInTheDocument();
    expect(screen.getByText("males sterile · females fertile")).toBeInTheDocument();
    expect(screen.getByText("R-S1-01")).toBeInTheDocument();
    expect(screen.getByText("Reference image 1 shows a lion.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close panel" })).toHaveFocus();
    await userEvent.keyboard("{Escape}");
    expect(useUi.getState().panel).toBeNull();
  });
});
