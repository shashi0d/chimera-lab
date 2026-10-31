import { useMemo } from "react";
import { useGraph } from "../../graph/store";
import type { GraphNode } from "../../graph/types";
import { useRuns } from "../../runs/store";
import type { ParentInfo, Run } from "../../types/api";

function capitalise(s: string): string {
  return s ? s[0]!.toUpperCase() + s.slice(1) : s;
}

export function parentName(p: Pick<ParentInfo, "match" | "reading">): string | null {
  const n = p.match?.commonName ?? p.reading.commonName;
  return n ? capitalise(n) : null;
}

/** The species a run identified for this asset: newest run first, then Result versions. */
export function speciesFor(assetId: string | undefined, runs: Record<string, Run>, nodes: GraphNode[]): string | null {
  if (!assetId) return null;
  const specs = Object.values(runs)
    .filter((r) => r.result)
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
    .map((r) => r.result!.spec);
  for (const n of nodes) {
    if (n.type !== "result") continue;
    const versions = (n.data as { versions?: Array<{ spec?: { parents?: ParentInfo[] } }> }).versions ?? [];
    for (const v of [...versions].reverse()) if (v.spec) specs.push(v.spec as never);
  }
  for (const s of specs) {
    const p = (s.parents ?? []).find((x) => x.assetId === assetId);
    const name = p ? parentName(p) : null;
    if (name) return name;
  }
  return null;
}

export function useSpecies(assetId: string | undefined): string | null {
  const runs = useRuns((s) => s.runs);
  const nodes = useGraph((s) => s.nodes);
  return useMemo(() => speciesFor(assetId, runs, nodes), [assetId, runs, nodes]);
}

/** Which Fusion slot(s) this image feeds ("A", "B", "A · B"), or "" when unconnected. */
export function useSlotOf(nodeId: string): string {
  const edges = useGraph((s) => s.edges);
  return useMemo(
    () =>
      [...new Set(edges.filter((e) => e.source === nodeId && (e.targetPort === "a" || e.targetPort === "b")).map((e) => e.targetPort.toUpperCase()))]
        .sort()
        .join(" · "),
    [edges, nodeId],
  );
}
