import { useMemo } from "react";
import { useGraph } from "../../graph/store";

function capitalise(s: string): string {
  return s ? s[0]!.toUpperCase() + s.slice(1) : s;
}

/** Display form of an identified animal name ("indian pangolin" → "Indian pangolin"). */
export function displaySpecies(name: string | null | undefined): string | null {
  const n = name?.trim();
  return n ? capitalise(n) : null;
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
