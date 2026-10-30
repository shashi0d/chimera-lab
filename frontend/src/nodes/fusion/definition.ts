import { defineNode } from "../types";
import { FusionView } from "./NodeView";
import { FUSION_INPUTS, FUSION_OUTPUTS } from "./ports";
import type { FusionConfig, FusionData } from "./types";
import { validateFusion } from "./validate";

export const fusionNode = defineNode<FusionConfig, FusionData>({
  type: "fusion",
  version: 1,
  label: "Fusion",
  category: "process",
  icon: "fusion",
  addable: true,
  inputs: FUSION_INPUTS,
  outputs: FUSION_OUTPUTS,
  defaultConfig: {},
  defaultData: () => ({ activeRunId: null, runIds: [] }),
  validate: validateFusion,
  View: FusionView,
  runnable: true,
});
