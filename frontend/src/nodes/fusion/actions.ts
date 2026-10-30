import { copy } from "../../copy";
import { useGraph } from "../../graph/store";
import type { GraphNode } from "../../graph/types";
import { upstreamNode } from "../../graph/queries";
import { onRunUpdate } from "../../runs/store";
import type { Run } from "../../types/api";
import type { ImageInputData } from "../image-input/types";
import { createNode } from "../registry";
import type { ResultData, ResultVersion } from "../result/types";
import { LAYOUT } from "../../canvas/addImages";

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
  const pos = fusion ? { x: fusion.position.x + LAYOUT.resultDx, y: fusion.position.y - 20 } : { x: 0, y: 0 };
  const result = createNode("result", pos);
  g.addNodes([result], [{ id: `e-${result.id}`, source: fusionId, sourcePort: "out", target: result.id, targetPort: "in" }]);
  return result.id;
}

function flagInput(fusionId: string, slot: "A" | "B" | null, message: string | null): void {
  const g = useGraph.getState();
  for (const port of ["a", "b"] as const) {
    const up = upstreamNode(g, fusionId, port);
    if (!up) continue;
    const flagged = slot && port === slot.toLowerCase() ? message : null;
    if ((up.data as ImageInputData).flagged !== flagged) {
      g.updateNodeData<ImageInputData>(up.id, (d) => ({ ...d, flagged }));
    }
  }
}

function addVersion(fusionId: string, run: Run): void {
  if (!run.result) return;
  const resultId = ensureResultNode(fusionId);
  const g = useGraph.getState();
  const node = g.nodes.find((n) => n.id === resultId);
  const data = node?.data as ResultData | undefined;
  if (data?.versions.some((v) => v.runId === run.id)) return; // already applied (e.g. after reload)
  const version: ResultVersion = {
    runId: run.id,
    assetId: run.result.assetId,
    creatureId: run.result.creatureId,
    imageUrl: run.result.imageUrl,
    spec: run.result.spec,
    createdAt: run.updatedAt,
  };
  g.updateNodeData<ResultData>(resultId, (d) => {
    const versions = [...(d.versions ?? []), version];
    return { ...d, versions, selected: versions.length - 1, stale: false };
  });
  g.updateNodeData<ResultData>(fusionId, (d) => ({ ...d, stale: false }));
}

/** Fusion reacts to its runs: Result node + versions on success, input highlighting on failure. */
export function registerFusionRunHandler(): () => void {
  return onRunUpdate((nodeId, run) => {
    const node = useGraph.getState().nodes.find((n) => n.id === nodeId);
    if (node?.type !== "fusion") return;
    if (run.status === "queued" || run.status === "running") {
      flagInput(nodeId, null, null);
      ensureResultNode(nodeId);
    } else if (run.status === "succeeded") {
      addVersion(nodeId, run);
    } else if (run.status === "failed" && run.failedInput) {
      const msg = run.error?.code === "HUMAN_DETECTED" ? copy.nodes.imageInput.highlightHuman : copy.nodes.imageInput.highlight;
      flagInput(nodeId, run.failedInput, msg);
    }
  });
}
