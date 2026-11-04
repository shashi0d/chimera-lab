import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppErrorBoundary } from "../../src/app/AppErrorBoundary";
import { Banners } from "../../src/app/Banners";
import { NodeErrorBoundary } from "../../src/canvas/NodeErrorBoundary";
import { useConnectivity } from "../../src/connectivity/store";
import { useGraph } from "../../src/graph/store";
import { UnsupportedNodeView } from "../../src/nodes/unsupported/NodeView";

function Boom(): never {
  throw new Error("boom");
}

beforeEach(() => {
  vi.spyOn(console, "error").mockImplementation(() => undefined);
  useConnectivity.setState({ browserOnline: true, serverReachable: true, forced: null, status: "online" });
});

describe("broken states", () => {
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

describe("connectivity banners", () => {
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
