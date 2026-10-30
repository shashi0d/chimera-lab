import type { CreatureSpec } from "../../types/api";

export interface ResultVersion {
  runId: string;
  assetId: string;
  creatureId: string;
  imageUrl: string;
  spec: CreatureSpec;
  createdAt: string;
  /** Meta Responses API id of this generation, for future previous_response_id edits (L1-01). */
  metaResponseId?: string | null;
}

export interface ResultData extends Record<string, unknown> {
  versions: ResultVersion[];
  selected: number;
  stale?: boolean;
}

export type ResultConfig = Record<string, never>;

export const RESULT_INPUTS = [{ id: "in", label: "", accepts: ["creature" as const] }];
/** F2: a Result can feed downstream nodes (e.g. a Field card). */
export const RESULT_OUTPUTS = [{ id: "out", emits: "creature" as const }];

export function displayName(spec: CreatureSpec): string {
  return spec.name?.trim() || (spec.parents ?? []).map((p) => p.match?.commonName ?? p.reading.commonName ?? "?").join(" × ");
}
