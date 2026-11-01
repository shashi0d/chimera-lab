import { describe, expect, it } from "vitest";
import { validateFusion } from "../../src/nodes/fusion/validate";
import type { GraphNode } from "../../src/graph/types";
import type { FusionConfig, FusionData } from "../../src/nodes/fusion/types";
import { edge, fusion, img } from "./helpers";

const f = fusion("f") as GraphNode<FusionConfig, FusionData>;
const codes = (nodes: GraphNode[], edges = [edge("a", "f", "a"), edge("b", "f", "b")], connectivity: "online" | "offline" | "unreachable" = "online") =>
  validateFusion(f, { graph: { nodes: [...nodes, f], edges }, connectivity, readOnly: false }).map((i) => i.code);

describe("Fusion pre-run validation (TASKSHEET 7.2)", () => {
  it("is runnable with two prepared, distinct images", () => {
    expect(codes([img("a"), img("b")])).toEqual([]);
  });
  it("0 or 1 inputs blocks Fuse with a hint", () => {
    expect(codes([], [])).toEqual(["MISSING_INPUTS"]);
    expect(codes([img("a")], [edge("a", "f", "a")])).toEqual(["MISSING_INPUTS"]);
  });
  it("an input still preparing blocks Make creature", () => {
    expect(codes([img("a", { status: "processing" }), img("b")])).toEqual(["INPUT_PREPARING"]);
  });
  it("a typed name stands in for a missing photo (the contract's name fallback)", () => {
    const named = fusion("f", { names: { a: "", b: "horse" } }) as GraphNode<FusionConfig, FusionData>;
    const run = (n: GraphNode<FusionConfig, FusionData>, nodes: GraphNode[], edges = [edge("a", "f", "a")]) =>
      validateFusion(n, { graph: { nodes: [...nodes, n], edges }, connectivity: "online", readOnly: false }).map((i) => i.code);
    expect(run(named, [img("a")])).toEqual([]);
    const both = fusion("f", { names: { a: "lion", b: "Lion" } }) as GraphNode<FusionConfig, FusionData>;
    expect(run(both, [], [])).toEqual(["DUPLICATE_INPUTS"]);
    const short = fusion("f", { names: { a: "x", b: "horse" } }) as GraphNode<FusionConfig, FusionData>;
    expect(run(short, [], [])).toEqual(["MISSING_INPUTS"]);
  });
  it("an input in error blocks Fuse and points at it", () => {
    const issues = validateFusion(f, {
      graph: { nodes: [img("a", { status: "error" }), img("b"), f], edges: [edge("a", "f", "a"), edge("b", "f", "b")] },
      connectivity: "online",
      readOnly: false,
    });
    expect(issues[0]).toMatchObject({ code: "INPUT_BROKEN", nodeId: "a", severity: "block" });
  });
  it("same image twice (same sha256) is DUPLICATE_INPUTS", () => {
    expect(codes([img("a", { sha256: "same" }), img("b", { sha256: "same" })])).toEqual(["DUPLICATE_INPUTS"]);
  });
  it("offline and server-unreachable block Fuse", () => {
    expect(codes([img("a"), img("b")], undefined, "offline")).toEqual(["OFFLINE"]);
    expect(codes([img("a"), img("b")], undefined, "unreachable")).toEqual(["UNREACHABLE"]);
  });
});
