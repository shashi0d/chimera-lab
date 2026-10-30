import { useGraph } from "../../graph/store";
import type { Run } from "../../types/api";
import { displayName } from "../result/types";
import type { FieldCardData } from "./types";

/** On success the card text is written into the node (it is part of the saved canvas). */
export function handleFieldCardRun(nodeId: string, run: Run): void {
  if (run.status !== "succeeded" || !run.result?.card) return;
  const { card, creatureId, imageUrl, spec } = run.result;
  useGraph.getState().updateNodeData<FieldCardData>(nodeId, (d) => ({ ...d, card, creatureId, imageUrl, name: displayName(spec) }));
}
