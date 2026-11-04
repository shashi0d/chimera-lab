import { defineNode } from "../types";
import { handleFusionRun } from "./actions";
import { FusionView } from "./NodeView";
import { FUSION_INPUTS, FUSION_OUTPUTS } from "./ports";
import { readStyle, type FusionConfig, type FusionData } from "./types";
import { validateFusion } from "./validate";

export const fusionNode = defineNode<FusionConfig, FusionData>({
  type: "fusion",
  version: 3, // v3: art style and name fallbacks (older versions' runs are dropped on load)
  label: "Fusion",
  category: "process",
  icon: "fusion",
  addable: true,
  inputs: FUSION_INPUTS,
  outputs: FUSION_OUTPUTS,
  defaultConfig: { style: "real" },
  defaultData: () => ({ activeRunId: null, runIds: [], names: { a: "", b: "" } }),
  validate: validateFusion,
  View: FusionView,
  runnable: true,
  onRunUpdate: handleFusionRun,
  migrate: (oldConfig, oldData) => {
    // v1/v2 runs were v1 pipeline runs: they can't be followed on the agent API, so they are dropped.
    const d = (oldData ?? {}) as FusionData;
    return { config: { style: readStyle(oldConfig) }, data: { ...d, activeRunId: null, runIds: [], names: d.names ?? { a: "", b: "" } } };
  },
});
