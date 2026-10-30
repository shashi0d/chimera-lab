import { copy } from "../../copy";
import type { GraphNode } from "../../graph/types";
import type { ValidationContext, ValidationIssue } from "../types";
import type { FieldCardConfig, FieldCardData } from "./types";
import { upstreamVersion } from "./upstream";

const t = copy.nodes.fieldCard;

export function validateFieldCard(node: GraphNode<FieldCardConfig, FieldCardData>, ctx: ValidationContext): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  if (ctx.readOnly) issues.push({ code: "READ_ONLY", message: copy.nodes.fusion.readOnly, severity: "block" });
  const up = upstreamVersion(ctx.graph, node.id);
  if (!up.result) issues.push({ code: "MISSING_INPUTS", message: t.hintNoInput, severity: "block" });
  else if (!up.version) issues.push({ code: "NO_VERSION", message: t.hintNoVersion, severity: "block" });
  if (ctx.connectivity === "offline") issues.push({ code: "OFFLINE", message: t.offline, severity: "block" });
  else if (ctx.connectivity === "unreachable") issues.push({ code: "UNREACHABLE", message: copy.nodes.fusion.unreachable, severity: "block" });
  return issues;
}
