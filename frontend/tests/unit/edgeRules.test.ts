import { describe, expect, it } from "vitest";
import { checkConnection } from "../../src/graph/edgeRules";
import { portsOf } from "../../src/nodes/registry";
import { edge, fusion, img, result } from "./helpers";

const graph = (edges = [edge("a", "f", "a")]) => ({ nodes: [img("a"), img("b"), fusion("f"), result("r")], edges });

describe("edge rules (TASKSHEET 4.1, 7.2)", () => {
  it("accepts image -> fusion input", () => {
    expect(checkConnection(graph(), { source: "b", sourcePort: "out", target: "f", targetPort: "b" }, portsOf)).toEqual({ ok: true });
  });
  it("accepts fusion -> image card", () => {
    expect(checkConnection(graph(), { source: "f", sourcePort: "out", target: "r", targetPort: "in" }, portsOf).ok).toBe(true);
  });
  it("the Lab path: image card -> edit -> image card; a photo never feeds an image card or an edit; an image card can feed a Fusion or an animal card", () => {
    const g = { nodes: [img("a"), fusion("f"), result("r"), { ...result("r2") }, { id: "e", type: "edit", version: 1, position: { x: 0, y: 0 }, config: { operation: "revise", instruction: "" }, data: {} }], edges: [] };
    expect(checkConnection(g, { source: "r", sourcePort: "out", target: "e", targetPort: "in" }, portsOf).ok).toBe(true);
    expect(checkConnection(g, { source: "e", sourcePort: "out", target: "r2", targetPort: "in" }, portsOf).ok).toBe(true);
    expect(checkConnection(g, { source: "a", sourcePort: "out", target: "e", targetPort: "in" }, portsOf)).toEqual({ ok: false, reason: "type" });
    expect(checkConnection(g, { source: "r", sourcePort: "out", target: "f", targetPort: "a" }, portsOf).ok).toBe(true);
    const withCard = { ...g, nodes: [...g.nodes, { id: "c", type: "card", version: 1, position: { x: 0, y: 0 }, config: {}, data: {} }] };
    expect(checkConnection(withCard, { source: "r", sourcePort: "out", target: "c", targetPort: "in" }, portsOf).ok).toBe(true);
    expect(checkConnection(withCard, { source: "a", sourcePort: "out", target: "c", targetPort: "in" }, portsOf)).toEqual({ ok: false, reason: "type" });
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
