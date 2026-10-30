import type { PortSpec } from "../../graph/types";

export const FUSION_INPUTS: PortSpec[] = [
  { id: "a", label: "A", accepts: ["image"] },
  { id: "b", label: "B", accepts: ["image"] },
];
export const FUSION_OUTPUTS: PortSpec[] = [{ id: "out", emits: "creature" }];
