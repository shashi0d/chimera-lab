import { defineNode } from "../types";
import { handleFusionRun } from "./actions";
import { FusionView } from "./NodeView";
import { FUSION_INPUTS, FUSION_OUTPUTS } from "./ports";
import { AUTO_DONORS, readDonors, type FusionConfig, type FusionData } from "./types";
import { validateFusion } from "./validate";

export const fusionNode = defineNode<FusionConfig, FusionData>({
  type: "fusion",
  version: 2, // v2 adds anatomy pins (F1)
  label: "Fusion",
  category: "process",
  icon: "fusion",
  addable: true,
  inputs: FUSION_INPUTS,
  outputs: FUSION_OUTPUTS,
  defaultConfig: { donors: { ...AUTO_DONORS } },
  defaultData: () => ({ activeRunId: null, runIds: [] }),
  validate: validateFusion,
  View: FusionView,
  runnable: true,
  onRunUpdate: handleFusionRun,
  migrate: (oldConfig, oldData) => ({
    // v1 had no config; v2 starts every part on "auto" and sanitises anything odd.
    config: { donors: readDonors(oldConfig) },
    data: (oldData ?? {}) as FusionData,
  }),
});
