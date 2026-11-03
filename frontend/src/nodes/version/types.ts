import type { PortSpec } from "../../graph/types";
import type { LabVersion } from "../../lab/api";

/** One image on the canvas: version 1 from a Fusion run, or the result of an edit card. */
export interface VersionData extends Record<string, unknown> {
  /** Set once the server has the version (a Fusion card waits for its run to finish). */
  version: LabVersion | null;
  /** The Fusion run this card waits for, before `version` exists. */
  runId?: string | null;
  error?: string | null;
}

export type VersionConfig = Record<string, never>;

export const VERSION_INPUTS: PortSpec[] = [{ id: "in", accepts: ["creature", "version"] }];
export const VERSION_OUTPUTS: PortSpec[] = [{ id: "out", emits: "version" }];
