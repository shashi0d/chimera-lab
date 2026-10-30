import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { useConnectivity } from "../../src/connectivity/store";
import { useGraph } from "../../src/graph/store";
import { useRuns } from "../../src/runs/store";
import type { CreatureSpec } from "../../src/types/api";
import { useUi } from "../../src/ui/uiStore";
import { edge, fusion, img, result, seed } from "../unit/helpers";
import { renderNode } from "./render";

beforeEach(() => {
  useConnectivity.setState({ browserOnline: true, serverReachable: true, forced: null, status: "online" });
  useRuns.setState({ runs: {}, startErrors: {}, starting: {} });
  useUi.setState({ panel: null });
});

describe("Image input node (TASKSHEET 7.1, 7.3)", () => {
  it("shows upload progress with percent and a cancel button", () => {
    seed([img("a", { upload: { status: "uploading", progress: 0.42 }, assetId: undefined })]);
    renderNode("a");
    expect(screen.getByRole("progressbar", { name: "Uploading 42%" })).toHaveAttribute("value", "42");
    expect(screen.getByRole("button", { name: "Cancel upload" })).toBeInTheDocument();
  });

  it("queued offline uploads explain they will start on reconnect", () => {
    seed([img("a", { upload: { status: "queued", progress: 0 }, assetId: undefined })]);
    renderNode("a");
    expect(screen.getByText(/Upload starts when you're back online/)).toBeInTheDocument();
  });

  it("server-side rejection shows what to change", () => {
    seed([img("a", { upload: { status: "error", progress: 0, error: { code: "IMAGE_TOO_SMALL", message: "x", retryable: false } } })]);
    renderNode("a");
    expect(screen.getByRole("alert")).toHaveTextContent("at least 256 px");
    expect(screen.queryByRole("button", { name: "Retry upload" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Replace image" }).length).toBeGreaterThan(0);
  });

  it("network failures can be retried", () => {
    seed([img("a", { upload: { status: "error", progress: 0, error: { code: "INTERNAL", message: "x", retryable: true } } })]);
    renderNode("a");
    expect(screen.getByRole("button", { name: "Retry upload" })).toBeInTheDocument();
  });

  it("a flagged input (NOT_AN_ANIMAL) is highlighted with text, not only color", () => {
    seed([img("a", { flagged: "This image isn't usable for fusion." })]);
    renderNode("a");
    expect(screen.getByText(/isn't usable for fusion/)).toBeInTheDocument();
    expect(screen.getByRole("article")).toHaveClass("is-flagged");
  });

  it("delete from the hover toolbar removes the node", async () => {
    seed([img("a")]);
    renderNode("a");
    await userEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(useGraph.getState().nodes).toHaveLength(0);
  });
});

const spec = (over: Partial<CreatureSpec> = {}): CreatureSpec => ({
  parents: [
    { slot: "A", assetId: "a", reading: { isAnimal: true, containsHuman: false, commonName: "Lion", scientificName: "Panthera leo", confidence: 0.9, visibleParts: [], bodyPlan: "quadruped", notes: "" }, match: null },
    { slot: "B", assetId: "b", reading: { isAnimal: true, containsHuman: false, commonName: "Tiger", scientificName: "Panthera tigris", confidence: 0.9, visibleParts: [], bodyPlan: "quadruped", notes: "" }, match: null },
  ],
  realHybrid: null,
  bodyPlan: "quadruped",
  partDonors: { head: "A", body: "B", limbs: "B", covering: "A", tail: "A" },
  rationale: "",
  name: "Leotigris",
  warnings: [],
  prompt: "Reference image 1 shows a lion.",
  model: { vision: "v", image: "i" },
  donorSource: {},
  ...over,
});
const version = (n: number, s = spec()) => ({ runId: `run${n}`, assetId: `ast${n}`, creatureId: `c${n}`, imageUrl: `/assets/ast${n}/content`, spec: s, createdAt: "" });

describe("Result node (TASKSHEET 7.4)", () => {
  it("always labels the image as a generated fusion", () => {
    seed([result("r", { versions: [version(1)], selected: 0 })]);
    renderNode("r");
    expect(screen.getByText("Generated fusion")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Generated fusion image: Leotigris. Not a real animal./ })).toBeInTheDocument();
  });

  it("shows the real-hybrid badge and warnings count", () => {
    const s = spec({
      realHybrid: { hybridId: "liger", name: "Liger", facts: {} },
      warnings: [{ ruleId: "R-A1-01", message: "m", severity: "warning" }, { ruleId: "R-T1-02", message: "m", severity: "info" }],
    });
    seed([result("r", { versions: [version(1, s)], selected: 0 })]);
    renderNode("r");
    expect(screen.getByText(/Real hybrid exists: Liger/)).toBeInTheDocument();
    expect(screen.getAllByText("1 field note").length).toBeGreaterThan(0);
  });

  it("switches between versions and keeps old ones", async () => {
    seed([result("r", { versions: [version(1), version(2, spec({ name: "Second" }))], selected: 1 })]);
    renderNode("r");
    expect(screen.getByRole("heading", { name: "Second" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Previous version" }));
    expect(screen.getByRole("heading", { name: "Leotigris" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous version" })).toBeDisabled();
  });

  it("falls back to a retry tile when the image fails to load", async () => {
    seed([result("r", { versions: [version(1)], selected: 0 })]);
    renderNode("r");
    fireEvent.error(screen.getByRole("img", { name: /Generated fusion image/ }));
    expect(screen.getByText("The image didn't load.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Reload image" }));
    expect(screen.getByRole("img", { name: /Generated fusion image/ }).getAttribute("src")).toContain("retry=1");
  });

  it("shows a skeleton while the upstream fusion is generating", () => {
    useRuns.getState().upsert({ id: "run9", graphId: "g", nodeId: "f", sessionId: null, status: "running", steps: [], result: null, error: null, failedInput: null, createdAt: "", updatedAt: "", version: 1 });
    seed([fusion("f", { activeRunId: "run9" }), result("r")], [edge("f", "r", "in")]);
    renderNode("r");
    expect(screen.getByLabelText("Generating…")).toBeInTheDocument();
  });

  it("opens the How this was made panel", async () => {
    seed([result("r", { versions: [version(1)], selected: 0 })]);
    renderNode("r");
    await userEvent.click(screen.getByRole("button", { name: "How this was made" }));
    expect(useUi.getState().panel).toEqual({ nodeId: "r" });
  });
});
