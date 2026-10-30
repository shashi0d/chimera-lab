import type { RunnableData } from "../../runs/store";

export const PARTS = ["head", "body", "limbs", "covering", "tail"] as const;
export type Part = (typeof PARTS)[number];
export type DonorPin = "auto" | "A" | "B";

export type FusionData = RunnableData;

/** v2 (F1): the user can pin each body part to a parent; "auto" lets the model decide. */
export interface FusionConfig extends Record<string, unknown> {
  donors: Record<Part, DonorPin>;
}

export const AUTO_DONORS: Record<Part, DonorPin> = { head: "auto", body: "auto", limbs: "auto", covering: "auto", tail: "auto" };

/** Tolerant read: anything unexpected becomes "auto". */
export function readDonors(config: unknown): Record<Part, DonorPin> {
  const raw = (config as { donors?: Record<string, unknown> } | null)?.donors ?? {};
  const out = { ...AUTO_DONORS };
  for (const p of PARTS) {
    const v = raw[p];
    if (v === "A" || v === "B" || v === "auto") out[p] = v;
  }
  return out;
}
