/** One finished agent run shown on the Result node (R1). The full card is GET /evo/creatures/{id}. */
export interface ResultVersion {
  runId: string;
  creatureId: string;
  imageUrl: string;
  title: string;
  createdAt: string;
}

export interface ResultData extends Record<string, unknown> {
  versions: ResultVersion[];
  selected: number;
  stale?: boolean;
}

export type ResultConfig = Record<string, never>;

export const RESULT_INPUTS = [{ id: "in", label: "", accepts: ["creature" as const] }];
export const RESULT_OUTPUTS: Array<{ id: string; emits: "creature" }> = [];
