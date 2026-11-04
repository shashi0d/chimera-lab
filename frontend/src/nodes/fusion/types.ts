import { STYLES, type Style } from "../../evo/types";

/** Fields every runnable node keeps in its data (convention shared with the registry). */
export interface RunnableData extends Record<string, unknown> {
  activeRunId?: string | null;
  runIds?: string[];
  stale?: boolean;
}

/** The art style; a typed animal name is used for a slot that has no photo or image connected. */
export interface FusionConfig extends Record<string, unknown> {
  /** Older canvases have none: "real". */
  style?: Style;
}

export interface FusionData extends RunnableData {
  /** Typed names, used for a slot with no photo connected (the contract's name fallback). */
  names?: { a: string; b: string };
}

export function readStyle(config: unknown): Style {
  const s = (config as { style?: unknown } | null)?.style;
  return STYLES.includes(s as Style) ? (s as Style) : "real";
}

/** A name the API can resolve: at least two letters, at most 60 characters. */
export function cleanName(raw: string | undefined | null): string | null {
  const n = (raw ?? "").replace(/\s+/g, " ").trim();
  return n.length >= 2 && n.length <= 60 && /\p{L}/u.test(n) ? n : null;
}
