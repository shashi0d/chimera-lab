import { copy } from "../../copy";
import { upstreamNode } from "../../graph/queries";
import type { GraphNode } from "../../graph/types";
import type { ImageInputData } from "../image-input/types";
import type { ValidationContext, ValidationIssue } from "../types";
import type { FusionConfig, FusionData } from "./types";

const t = copy.nodes.fusion;

/** Pre-run checks (TASKSHEET 7.2). Any "block" issue disables Fuse and becomes the hint. */
export function validateFusion(node: GraphNode<FusionConfig, FusionData>, ctx: ValidationContext): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  if (ctx.readOnly) issues.push({ code: "READ_ONLY", message: t.readOnly, severity: "block" });
  const inputs = (["a", "b"] as const).map((port) => ({ port, node: upstreamNode(ctx.graph, node.id, port) }));
  const connected = inputs.filter((i) => i.node);
  if (connected.length === 0) issues.push({ code: "MISSING_INPUTS", message: t.waitingInputs, severity: "block" });
  else if (connected.length === 1) issues.push({ code: "MISSING_INPUTS", message: t.needOneMore, severity: "block" });
  for (const { port, node: up } of inputs) {
    if (!up) continue;
    const d = up.data as ImageInputData;
    const slot = port.toUpperCase();
    if (d.upload?.status === "error" || d.upload?.status === "cancelled") {
      issues.push({ code: "INPUT_BROKEN", message: t.brokenInput(slot), severity: "block", nodeId: up.id });
    } else if (d.upload?.status !== "done" || !d.assetId) {
      issues.push({ code: "INPUT_UPLOADING", message: t.stillUploading, severity: "block", nodeId: up.id });
    }
  }
  const [a, b] = inputs.map((i) => i.node?.data as ImageInputData | undefined);
  if (a?.sha256 && b?.sha256 && (a.sha256 === b.sha256 || a.assetId === b.assetId)) {
    issues.push({ code: "DUPLICATE_INPUTS", message: t.duplicate, severity: "block" });
  }
  if (ctx.connectivity === "offline") issues.push({ code: "OFFLINE", message: t.offline, severity: "block" });
  else if (ctx.connectivity === "unreachable") issues.push({ code: "UNREACHABLE", message: t.unreachable, severity: "block" });
  return issues;
}
