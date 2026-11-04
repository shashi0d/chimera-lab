import { defineNode } from "../types";
import { EditView } from "./NodeView";
import { EDIT_INPUTS, EDIT_OUTPUTS, type EditConfig, type EditData } from "./types";

export const editNode = defineNode<EditConfig, EditData>({
  type: "edit",
  version: 1,
  label: "Edit",
  category: "process",
  icon: "replace",
  addable: false, // added from an image card (Revise, Paint) or by dragging from its output
  inputs: EDIT_INPUTS,
  outputs: EDIT_OUTPUTS,
  defaultConfig: { operation: "revise", instruction: "" },
  defaultData: () => ({ jobIds: [], activeJobId: null, error: null, hasMask: false }),
  validate: (node, ctx) => {
    const issues = [];
    if (!ctx.graph.edges.some((e) => e.target === node.id && e.targetPort === "in")) {
      issues.push({ code: "NO_IMAGE", message: "Connect an image to edit.", severity: "block" as const });
    }
    if (!node.config.instruction.trim() && node.config.operation !== "sketch") {
      issues.push({ code: "NO_INSTRUCTION", message: "Describe the change.", severity: "block" as const });
    }
    if (node.config.operation === "sketch" && !node.data.hasSketch) {
      issues.push({ code: "NO_SKETCH", message: "Draw on the image first.", severity: "block" as const });
    }
    if (node.config.operation === "paint" && !node.data.hasMask) {
      issues.push({ code: "NO_MASK", message: "Paint the area to change.", severity: "block" as const });
    }
    return issues;
  },
  View: EditView,
  runnable: true,
});
