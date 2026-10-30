import { defineNode } from "../types";
import { ResultView } from "./NodeView";
import { ResultPanel } from "./Panel";
import { RESULT_INPUTS, type ResultConfig, type ResultData } from "./types";

export const resultNode = defineNode<ResultConfig, ResultData>({
  type: "result",
  version: 1,
  label: "Result",
  category: "output",
  icon: "result",
  addable: false, // created by the Fusion node when it runs
  inputs: RESULT_INPUTS,
  outputs: [],
  defaultConfig: {},
  defaultData: () => ({ versions: [], selected: 0 }),
  validate: () => [],
  View: ResultView,
  Panel: ResultPanel,
  runnable: false,
});
