import { MODES, STYLES, type Mode, type Style } from "../../evo/types";

/** Fields every runnable node keeps in its data (convention shared with the registry). */
export interface RunnableData extends Record<string, unknown> {
  activeRunId?: string | null;
  runIds?: string[];
  stale?: boolean;
}

/** v3 (R1): the agent API takes a mode, and a typed animal name for a slot that has no photo. */
export interface FusionConfig extends Record<string, unknown> {
  mode: Mode;
  /** The art style (prompt mode). Older canvases have none: "real". */
  style?: Style;
}

export interface FusionData extends RunnableData {
  /** Typed names, used for a slot with no photo connected (the contract's name fallback). */
  names?: { a: string; b: string };
}

export function readMode(config: unknown): Mode {
  const m = (config as { mode?: unknown } | null)?.mode;
  return MODES.includes(m as Mode) ? (m as Mode) : "realistic";
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
