import { defineNode } from "../types";
import { ResultView } from "./NodeView";
import { RESULT_INPUTS, RESULT_OUTPUTS, type ResultConfig, type ResultData } from "./types";

export const resultNode = defineNode<ResultConfig, ResultData>({
  type: "result",
  version: 2, // v2 (R1): versions are agent creatures; v1 pipeline versions can't open a creature card and are dropped
  label: "Result",
  category: "output",
  icon: "result",
  addable: false, // created by the Fusion node when it runs
  inputs: RESULT_INPUTS,
  outputs: RESULT_OUTPUTS,
  defaultConfig: {},
  defaultData: () => ({ versions: [], selected: 0 }),
  validate: () => [],
  View: ResultView,
  runnable: false,
  migrate: () => ({ config: {}, data: { versions: [], selected: 0 } }),
});
