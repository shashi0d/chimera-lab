import { defineNode } from "../types";
import { VersionView } from "./NodeView";
import { VERSION_INPUTS, VERSION_OUTPUTS, type VersionConfig, type VersionData } from "./types";

export const versionNode = defineNode<VersionConfig, VersionData>({
  type: "version",
  version: 1,
  label: "Image",
  category: "output",
  icon: "result",
  addable: false, // made by a Fusion run or an edit card
  inputs: VERSION_INPUTS,
  outputs: VERSION_OUTPUTS,
  defaultConfig: {},
  defaultData: () => ({ version: null, runId: null, error: null }),
  validate: () => [],
  View: VersionView,
  runnable: false,
});
