import { wouldCreateCycle } from "./queries";
import type { GraphDoc, PortSpec } from "./types";

export interface ConnectionAttempt {
  source: string;
  sourcePort: string;
  target: string;
  targetPort: string;
}

export type RefusalReason = "self" | "type" | "occupied" | "cycle" | "unknown";
export type ConnectionCheck = { ok: true } | { ok: false; reason: RefusalReason };

export type PortLookup = (nodeType: string) => { inputs: PortSpec[]; outputs: PortSpec[] } | undefined;

/**
 * Edge rule (TASKSHEET 4.1): allowed only if the source port's `emits` is in the
 * target port's `accepts`, the target port is free (unless it allows many), and
 * the edge would not create a cycle.
 */
export function checkConnection(graph: Pick<GraphDoc, "nodes" | "edges">, c: ConnectionAttempt, ports: PortLookup): ConnectionCheck {
  if (c.source === c.target) return { ok: false, reason: "self" };
  const src = graph.nodes.find((n) => n.id === c.source);
  const tgt = graph.nodes.find((n) => n.id === c.target);
  if (!src || !tgt) return { ok: false, reason: "unknown" };
  const out = ports(src.type)?.outputs.find((p) => p.id === c.sourcePort);
  const inp = ports(tgt.type)?.inputs.find((p) => p.id === c.targetPort);
  if (!out || !inp || !out.emits || !inp.accepts?.includes(out.emits)) return { ok: false, reason: "type" };
  if (!inp.many && graph.edges.some((e) => e.target === c.target && e.targetPort === c.targetPort)) {
    return { ok: false, reason: "occupied" };
  }
  if (wouldCreateCycle(graph, c.source, c.target)) return { ok: false, reason: "cycle" };
  return { ok: true };
}
