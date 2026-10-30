import type { PortSpec } from "../../graph/types";

export const IMAGE_INPUT_INPUTS: PortSpec[] = [];
export const IMAGE_INPUT_OUTPUTS: PortSpec[] = [{ id: "out", emits: "image" }];
