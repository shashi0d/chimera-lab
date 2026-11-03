import type { DerivedRun } from "../../evo/runs";
import { useGraph } from "../../graph/store";
import { ensureRunVersion } from "../../lab/store";
import type { FusionData } from "./types";

export function creatureTitle(run: Pick<DerivedRun, "sire" | "dam">): string {
  return run.sire && run.dam ? `${run.sire.commonName} × ${run.dam.commonName}` : "";
}

/** Fusion reacts to its runs: each run has an image card after it, filled with version 1 when the run finishes. */
export function handleFusionRun(nodeId: string, run: DerivedRun): void {
  const fusion = useGraph.getState().nodes.find((n) => n.id === nodeId);
  if (!fusion || !((fusion.data as FusionData).runIds ?? []).includes(run.runId)) return;
  if (run.status === "loading") return;
  ensureRunVersion(nodeId, run.runId, Boolean(run.finalize));
}
