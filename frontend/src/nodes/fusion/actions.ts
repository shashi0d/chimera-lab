import { findFreeSpot, FOOTPRINT, LAYOUT } from "../../canvas/addImages";
import type { DerivedRun } from "../../evo/runs";
import { useGraph } from "../../graph/store";
import type { GraphNode } from "../../graph/types";
import { createNode } from "../registry";
import type { ResultData, ResultVersion } from "../result/types";
import type { FusionData } from "./types";

function resultNodeFor(fusionId: string): GraphNode | undefined {
  const g = useGraph.getState();
  const edge = g.edges.find((e) => e.source === fusionId && e.sourcePort === "out");
  const node = edge ? g.nodes.find((n) => n.id === edge.target) : undefined;
  return node?.type === "result" ? node : undefined;
}

/** Make sure a Result node hangs off this Fusion node (created when the first run starts). */
export function ensureResultNode(fusionId: string): string {
  const existing = resultNodeFor(fusionId);
  if (existing) return existing.id;
  const g = useGraph.getState();
  const fusion = g.nodes.find((n) => n.id === fusionId);
  const want = fusion ? { x: fusion.position.x + LAYOUT.resultDx, y: fusion.position.y - 20 } : { x: 0, y: 0 };
  const pos = findFreeSpot(want, FOOTPRINT.result!.w, FOOTPRINT.result!.h);
  const result = createNode("result", pos);
  g.addNodes([result], [{ id: `e-${result.id}`, source: fusionId, sourcePort: "out", target: result.id, targetPort: "in" }]);
  return result.id;
}

export function creatureTitle(run: Pick<DerivedRun, "sire" | "dam">): string {
  return run.sire && run.dam ? `${run.sire.commonName} × ${run.dam.commonName}` : "";
}

/** Fusion reacts to its runs: the finished creature becomes a new version on its Result node. */
export function handleFusionRun(nodeId: string, run: DerivedRun): void {
  const fin = run.finalize;
  if (!fin) return;
  const fusion = useGraph.getState().nodes.find((n) => n.id === nodeId);
  if (!fusion || !((fusion.data as FusionData).runIds ?? []).includes(run.runId)) return;
  const resultId = ensureResultNode(nodeId);
  const g = useGraph.getState();
  const data = g.nodes.find((n) => n.id === resultId)?.data as ResultData | undefined;
  if (data?.versions.some((v) => v.runId === run.runId)) return; // already applied (e.g. after reload)
  const version: ResultVersion = { runId: run.runId, creatureId: fin.creatureId, imageUrl: fin.imageUrl, title: creatureTitle(run), createdAt: fin.at };
  g.updateNodeData<ResultData>(resultId, (d) => {
    const versions = [...(d.versions ?? []), version];
    return { ...d, versions, selected: versions.length - 1, stale: false };
  });
}
