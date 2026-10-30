import type { RunnableData } from "../../runs/store";
import type { FieldCard } from "../../types/api";

export interface FieldCardData extends RunnableData {
  card?: FieldCard | null;
  /** Creature the card was written for (compared with the Result's selected version). */
  creatureId?: string;
  imageUrl?: string;
  name?: string;
}

export type FieldCardConfig = Record<string, never>;

export const FIELD_CARD_INPUTS = [{ id: "in", label: "", accepts: ["creature" as const] }];
