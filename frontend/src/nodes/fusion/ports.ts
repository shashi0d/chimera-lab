import type { PortSpec } from "../../graph/types";

export const FUSION_INPUTS: PortSpec[] = [
  // A photo, or an earlier generated creature (an image card's output).
  { id: "a", label: "A", accepts: ["image", "version"] },
  { id: "b", label: "B", accepts: ["image", "version"] },
];
export const FUSION_OUTPUTS: PortSpec[] = [{ id: "out", emits: "creature" }];
