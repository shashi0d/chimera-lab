import type { PortSpec } from "../../graph/types";

export type EditOperation = "revise" | "paint";

/** What to change. Paint also has a mask, kept on this device (IndexedDB) until it is sent. */
export interface EditConfig extends Record<string, unknown> {
  operation: EditOperation;
  instruction: string;
}

export interface EditData extends Record<string, unknown> {
  /** Every job this card started (each success adds an image card after it). */
  jobIds: string[];
  activeJobId: string | null;
  error: string | null;
  /** A painted mask is saved for this card. */
  hasMask?: boolean;
}

export const EDIT_INPUTS: PortSpec[] = [{ id: "in", accepts: ["version"] }];
export const EDIT_OUTPUTS: PortSpec[] = [{ id: "out", emits: "version" }];

export function maskKey(nodeId: string): string {
  return `mask:${nodeId}`;
}
