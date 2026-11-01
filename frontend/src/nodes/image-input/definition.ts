import { defineNode } from "../types";
import { ImageInputView } from "./NodeView";
import { IMAGE_INPUT_INPUTS, IMAGE_INPUT_OUTPUTS } from "./ports";
import { migrateImageData, type ImageInputConfig, type ImageInputData } from "./types";

export const imageInputNode = defineNode<ImageInputConfig, ImageInputData>({
  type: "image-input",
  version: 2, // v2 (R1): local copy only, no server upload
  label: "Image",
  category: "input",
  icon: "image",
  addable: false, // added via drop / paste / the "Add image" picker instead
  inputs: IMAGE_INPUT_INPUTS,
  outputs: IMAGE_INPUT_OUTPUTS,
  defaultConfig: {},
  defaultData: () => ({ fileName: "", status: "processing", error: null }),
  validate: () => [],
  View: ImageInputView,
  runnable: false,
  migrate: (_config, data) => ({ config: {}, data: migrateImageData(data) }),
});
