import { defineNode } from "../types";
import { ImageInputView } from "./NodeView";
import { IMAGE_INPUT_INPUTS, IMAGE_INPUT_OUTPUTS } from "./ports";
import type { ImageInputConfig, ImageInputData } from "./types";

export const imageInputNode = defineNode<ImageInputConfig, ImageInputData>({
  type: "image-input",
  version: 1,
  label: "Image",
  category: "input",
  icon: "image",
  addable: false, // added via drop / paste / the "Add image" picker instead
  inputs: IMAGE_INPUT_INPUTS,
  outputs: IMAGE_INPUT_OUTPUTS,
  defaultConfig: {},
  defaultData: () => ({ fileName: "", upload: { status: "processing", progress: 0, error: null } }),
  validate: () => [],
  View: ImageInputView,
  runnable: false,
});
