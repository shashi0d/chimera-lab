import { describe, expect, it } from "vitest";
import { checkConnection } from "../../src/graph/edgeRules";
import { portsOf } from "../../src/nodes/registry";
import { edge, fusion, img, result } from "./helpers";

const graph = (edges = [edge("a", "f", "a")]) => ({ nodes: [img("a"), img("b"), fusion("f"), result("r")], edges });

describe("edge rules (TASKSHEET 4.1, 7.2)", () => {
  it("accepts image -> fusion input", () => {
    expect(checkConnection(graph(), { source: "b", sourcePort: "out", target: "f", targetPort: "b" }, portsOf)).toEqual({ ok: true });
  });
  it("accepts fusion -> result", () => {
    expect(checkConnection(graph(), { source: "f", sourcePort: "out", target: "r", targetPort: "in" }, portsOf).ok).toBe(true);
  });
  it("refuses wrong port type", () => {
    expect(checkConnection(graph(), { source: "a", sourcePort: "out", target: "r", targetPort: "in" }, portsOf)).toEqual({ ok: false, reason: "type" });
  });
  it("refuses an already-connected single port", () => {
    expect(checkConnection(graph(), { source: "b", sourcePort: "out", target: "f", targetPort: "a" }, portsOf)).toEqual({ ok: false, reason: "occupied" });
  });
  it("refuses self connections", () => {
    expect(checkConnection(graph(), { source: "f", sourcePort: "out", target: "f", targetPort: "a" }, portsOf)).toEqual({ ok: false, reason: "self" });
  });
  it("refuses cycles", () => {
    const g = { nodes: [fusion("f1"), fusion("f2")], edges: [edge("f1", "f2", "a")] };
    // pretend fusion accepted creatures: use a custom port lookup to isolate the cycle check
    const ports = () => ({ inputs: [{ id: "a", accepts: ["creature" as const] }], outputs: [{ id: "out", emits: "creature" as const }] });
    expect(checkConnection(g, { source: "f2", sourcePort: "out", target: "f1", targetPort: "a" }, ports)).toEqual({ ok: false, reason: "cycle" });
  });
  it("refuses unknown nodes", () => {
    expect(checkConnection(graph(), { source: "x", sourcePort: "out", target: "f", targetPort: "b" }, portsOf).ok).toBe(false);
  });
});
