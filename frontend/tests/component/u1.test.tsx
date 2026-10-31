import { ReactFlowProvider } from "@xyflow/react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { SidePanel } from "../../src/app/SidePanel";
import { useConnectivity } from "../../src/connectivity/store";
import { useGraph } from "../../src/graph/store";
import { BODY_REGIONS } from "../../src/nodes/fusion/bodyRegions";
import { PARTS } from "../../src/nodes/fusion/types";
import { summarize } from "../../src/nodes/result/summary";
import { useRuns } from "../../src/runs/store";
import type { CreatureSpec, MythologyMatch, Run } from "../../src/types/api";
import { useUi } from "../../src/ui/uiStore";
import { edge, fusion, img, result, seed } from "../unit/helpers";
import { renderNode } from "./render";

// U1: image-first nodes, the body diagram and the "How this was made" drawer.

const griffin: MythologyMatch = {
  creatureName: "griffin",
  culture: "Greek",
  componentAnimals: "eagle|lion",
  componentParts: "eagle:head,wings|lion:body,tail",
  hasHumanPart: false,
  matched: { A: "eagle", B: "lion" },
  matchKind: { A: "name", B: "name" },
  verification: "line-checked by Muse (not re-checked by Claude)",
  verified: false,
  sourceUrl: "https://en.wikipedia.org/wiki/Griffin",
};

const spec = (over: Partial<CreatureSpec> = {}): CreatureSpec => ({
  parents: [
    {
      slot: "A",
      assetId: "ast_a",
      reading: {
        isAnimal: true,
        containsHuman: false,
        commonName: "Bald eagle",
        scientificName: "Haliaeetus leucocephalus",
        confidence: 0.97,
        visibleParts: [],
        bodyPlan: "biped",
        notes: "",
      },
      match: {
        animalId: "bald_eagle",
        tier: 1,
        commonName: "bald eagle",
        scientificName: "Haliaeetus leucocephalus",
        matchedOn: "scientific_name",
        facts: {},
      },
    },
    {
      slot: "B",
      assetId: "ast_b",
      reading: {
        isAnimal: true,
        containsHuman: false,
        commonName: "Lion",
        scientificName: "Panthera leo",
        confidence: 1,
        visibleParts: [],
        bodyPlan: "quadruped",
        notes: "",
      },
      match: {
        animalId: "lion",
        tier: 1,
        commonName: "lion",
        scientificName: "Panthera leo",
        matchedOn: "scientific_name",
        facts: {},
      },
    },
  ],
  realHybrid: null,
  realHybrids: [],
  mythology: [griffin],
  rulesSummary: { total: 130, run: 44 },
  bodyPlan: "quadruped",
  partDonors: { head: "A", body: "B", limbs: "B", covering: "B", tail: "B" },
  rationale: "Planner prose that should stay folded away.",
  name: "White-crowned Savanna Hunter",
  warnings: [
    {
      ruleId: "R-A8-02",
      message: "Body plans conflict.",
      severity: "warning",
      detail: null,
    },
  ],
  prompt: "Reference image 1 shows an eagle.",
  model: { vision: "v", image: "i" },
  donorSource: {},
  ...over,
});

const version = (s = spec()) => ({
  runId: "run1",
  assetId: "ast_r",
  creatureId: "c1",
  imageUrl: "/assets/ast_r/content",
  spec: s,
  createdAt: "",
});

function openDrawer() {
  useUi.getState().openPanel("r");
  render(
    <ReactFlowProvider>
      <SidePanel />
    </ReactFlowProvider>,
  );
  return screen.getByRole("complementary");
}

beforeEach(() => {
  useConnectivity.setState({
    browserOnline: true,
    serverReachable: true,
    forced: null,
    status: "online",
  });
  useRuns.setState({ runs: {}, startErrors: {}, starting: {} });
  useUi.setState({ panel: null });
});

describe("U1 image-first nodes", () => {
  it("an input is titled by its identified species, never its filename", () => {
    seed([img("a", { fileName: "IMG_2041.jpg" }), result("r", { versions: [version()] })]);
    renderNode("a");
    expect(screen.getByRole("heading", { name: "Bald eagle" })).toBeInTheDocument();
    expect(screen.queryByText("IMG_2041.jpg")).not.toBeInTheDocument();
    expect(screen.queryByText(/No\.\d/)).not.toBeInTheDocument();
  });

  it("an unidentified input says so plainly and names its slot", () => {
    seed([img("a", { fileName: "IMG_2041.jpg" }), fusion("f")], [edge("a", "f", "a")]);
    renderNode("a");
    expect(screen.getByRole("heading", { name: "Animal photo" })).toBeInTheDocument();
    expect(screen.getByText("Input A")).toBeInTheDocument();
  });

  it("the Fusion node shows portraits with species names, not dropdowns, and no result thumbnail", () => {
    const run: Run = {
      id: "run1",
      graphId: "g",
      nodeId: "f",
      sessionId: null,
      status: "succeeded",
      steps: [],
      error: null,
      failedInput: null,
      createdAt: "",
      updatedAt: "2026-10-30T00:00:00Z",
      version: 1,
      usage: {},
      result: {
        assetId: "ast_r",
        creatureId: "c1",
        imageUrl: "/assets/ast_r/content",
        spec: spec(),
        card: null,
        metaResponseId: null,
      },
    };
    useRuns.getState().upsert(run);
    seed([img("a"), img("b"), fusion("f", { activeRunId: "run1", runIds: ["run1"] })], [edge("a", "f", "a"), edge("b", "f", "b")]);
    renderNode("f");
    const parents = document.querySelector(".fusion-node__parents") as HTMLElement;
    expect(within(parents).getByText("Bald eagle")).toBeInTheDocument();
    expect(within(parents).getByText("Lion")).toBeInTheDocument();
    expect(within(parents).queryByRole("combobox")).not.toBeInTheDocument();
    // the keyboard slot selectors live in the contextual toolbar
    const toolbar = screen.getByRole("toolbar");
    expect(within(toolbar).getByLabelText("Connect image A")).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /Generated fusion image/ })).not.toBeInTheDocument();
  });

  it("the Result card leads with the creature name and its pills", () => {
    seed([
      result("r", {
        versions: [
          version(
            spec({
              realHybrid: {
                hybridId: "liger",
                name: "liger",
                facts: {},
                father: null,
                mother: null,
                cross: null,
                confidence: null,
                fertility: null,
                matchedVia: null,
              },
            }),
          ),
        ],
      }),
    ]);
    renderNode("r");
    expect(screen.getByRole("heading", { name: "White-crowned Savanna Hunter" })).toBeInTheDocument();
    expect(screen.getByText("Generated fusion")).toBeInTheDocument();
    expect(screen.getByText(/Real hybrid exists: liger/)).toBeInTheDocument();
    expect(screen.getByText("Result · v1")).toBeInTheDocument();
  });
});

describe("U1 body diagram", () => {
  it("is drawn from the region list, one button per part", () => {
    expect(BODY_REGIONS.map((r) => r.id).sort()).toEqual([...PARTS].sort());
    seed([img("a"), img("b"), fusion("f")], [edge("a", "f", "a"), edge("b", "f", "b")]);
    renderNode("f");
    for (const label of ["Head", "Body", "Limbs", "Covering", "Tail"]) {
      expect(
        screen.getByRole("button", {
          name: `${label} from Auto (model decides)`,
        }),
      ).toBeInTheDocument();
    }
  });

  it("Enter and Space cycle a region; a pinned region shows its donor letter", async () => {
    seed([img("a"), img("b"), fusion("f")], [edge("a", "f", "a"), edge("b", "f", "b")]);
    renderNode("f");
    screen.getByRole("button", { name: "Tail from Auto (model decides)" }).focus();
    await userEvent.keyboard("{Enter}");
    const tail = screen.getByRole("button", { name: "Tail from A" });
    expect(tail).toHaveFocus();
    expect(tail.querySelector(".body-region__badge-letter")?.textContent).toBe("A");
    await userEvent.keyboard(" ");
    expect(screen.getByRole("button", { name: "Tail from B" })).toBeInTheDocument();
    expect(
      (
        useGraph.getState().nodes.find((n) => n.id === "f")?.config as {
          donors: Record<string, string>;
        }
      ).donors.tail,
    ).toBe("B");
  });
});

describe("U1 drawer", () => {
  it("leads with a plain summary built from the spec", () => {
    const lines = summarize(spec());
    expect(lines).toHaveLength(3);
    expect(lines[0]).toBe("The head comes from the bald eagle; the body, limbs, covering and tail come from the lion.");
    expect(lines[1]).toContain("griffin");
    expect(lines[1]).toContain("unverified");
    expect(lines[2]).toBe("The anatomy rules raised 1 warning.");
  });

  it("shows stat cards; tokens read 'unknown' when not recorded, never 0", () => {
    seed([result("r", { versions: [version()] })]);
    const drawer = openDrawer();
    const stats = within(drawer).getByRole("group", { name: "Key numbers" });
    expect(within(stats).getByText("97%")).toBeInTheDocument();
    expect(within(stats).getByText("44")).toBeInTheDocument();
    expect(within(stats).getByText("unknown")).toBeInTheDocument();
    expect(within(stats).queryByText(/^0$/, { selector: ".stat__value" })).not.toBeInTheDocument();
  });

  it("tokens come from the run when it is known", () => {
    useRuns.getState().upsert({
      id: "run1",
      graphId: "g",
      nodeId: "f",
      sessionId: null,
      status: "succeeded",
      steps: [],
      result: null,
      error: null,
      failedInput: null,
      createdAt: "",
      updatedAt: "",
      version: 1,
      usage: { tokens: 28641 },
    });
    seed([result("r", { versions: [version()] })]);
    const drawer = openDrawer();
    expect(within(drawer).getByText("28,641")).toBeInTheDocument();
  });

  it("mythology is always marked unverified and never called verified or confirmed", () => {
    seed([
      result("r", {
        versions: [version(spec({ mythology: [{ ...griffin, verified: true }] }))],
      }),
    ]);
    const drawer = openDrawer();
    const myth = drawer.querySelector(".myth") as HTMLElement;
    expect(myth).toHaveTextContent("Resembles griffin (Greek)");
    expect(within(myth).getByText("Unverified")).toBeInTheDocument();
    expect(myth).toHaveTextContent("line-checked by Muse");
    expect(myth.textContent?.replace(/unverified/gi, "")).not.toMatch(/verified|confirmed/i);
  });

  it("the planner rationale is folded into a collapsed 'Planner notes' section", () => {
    seed([result("r", { versions: [version()] })]);
    const drawer = openDrawer();
    const notes = within(drawer).getByText("Planner notes").closest("details") as HTMLDetailsElement;
    expect(notes.open).toBe(false);
    expect(notes).toHaveTextContent("Planner prose");
  });
});
