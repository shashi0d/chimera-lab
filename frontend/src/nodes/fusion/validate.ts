import { copy } from "../../copy";
import { upstreamNode } from "../../graph/queries";
import type { GraphNode } from "../../graph/types";
import type { ImageInputData } from "../image-input/types";
import type { VersionData } from "../version/types";
import type { ValidationContext, ValidationIssue } from "../types";
import { cleanName, type FusionConfig, type FusionData } from "./types";

const t = copy.nodes.fusion;

/** Pre-run checks. Any "block" issue disables Make creature and becomes the visible reason. */
export function validateFusion(node: GraphNode<FusionConfig, FusionData>, ctx: ValidationContext): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  if (ctx.readOnly) issues.push({ code: "READ_ONLY", message: t.readOnly, severity: "block" });
  const names = node.data.names ?? { a: "", b: "" };
  const slots = (["a", "b"] as const).map((port) => ({ port, up: upstreamNode(ctx.graph, node.id, port), name: cleanName(names[port]) }));
  const missing = slots.filter((s) => !s.up && !s.name);
  if (missing.length === 2) issues.push({ code: "MISSING_INPUTS", message: t.waitingInputs, severity: "block" });
  else if (missing.length === 1) issues.push({ code: "MISSING_INPUTS", message: t.needOneMore(missing[0]!.port.toUpperCase()), severity: "block" });
  for (const { port, up } of slots) {
    if (!up) continue;
    const slot = port.toUpperCase();
    if (up.type === "version") {
      if (!(up.data as VersionData).version) issues.push({ code: "INPUT_PREPARING", message: t.imagePending, severity: "block", nodeId: up.id });
      continue;
    }
    const d = up.data as ImageInputData;
    if (d.status === "error") issues.push({ code: "INPUT_BROKEN", message: t.brokenInput(slot), severity: "block", nodeId: up.id });
    else if (d.status !== "ready" || !d.blobKey) issues.push({ code: "INPUT_PREPARING", message: t.stillPreparing, severity: "block", nodeId: up.id });
  }
  const [a, b] = slots.map((s) => (s.up?.type === "image-input" ? (s.up.data as ImageInputData) : undefined));
  if (slots[0]!.up && slots[0]!.up.type === "version" && slots[0]!.up.id === slots[1]!.up?.id) {
    issues.push({ code: "DUPLICATE_INPUTS", message: t.duplicate, severity: "block" });
  }
  if (a?.sha256 && b?.sha256 && a.sha256 === b.sha256) issues.push({ code: "DUPLICATE_INPUTS", message: t.duplicate, severity: "block" });
  if (!slots[0]!.up && !slots[1]!.up && slots[0]!.name && slots[1]!.name && slots[0]!.name.toLowerCase() === slots[1]!.name.toLowerCase()) {
    issues.push({ code: "DUPLICATE_INPUTS", message: t.duplicateNames, severity: "block" });
  }
  if (ctx.connectivity === "offline") issues.push({ code: "OFFLINE", message: t.offline, severity: "block" });
  else if (ctx.connectivity === "unreachable") issues.push({ code: "UNREACHABLE", message: t.unreachable, severity: "block" });
  return issues;
}
