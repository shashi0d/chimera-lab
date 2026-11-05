import { create } from "zustand";
import { toAppError, type AppError } from "../api/errors";
import { evo } from "./index";
import type { ImageQuota, Limits } from "./types";

// The Fusion limits: one small store so every screen shares one fetch.

type Load<T> = { status: "idle" | "loading" | "ready" | "error"; data: T | null; error: AppError | null };
const idle = <T,>(): Load<T> => ({ status: "idle", data: null, error: null });

// ------------------------------------------------------------------ limits

interface LimitsState extends Load<Limits> {
  /** Set when POST answered 429 CAP_REACHED, so the capped state shows even before limits refresh. */
  capError: AppError | null;
  refresh(): Promise<void>;
  setCapError(err: AppError | null): void;
}

export const useLimits = create<LimitsState>()((set) => ({
  ...idle<Limits>(),
  capError: null,
  async refresh() {
    set((s) => ({ status: s.data ? s.status : "loading" }));
    try {
      const data = await evo().getLimits();
      set({ status: "ready", data, error: null });
    } catch (e) {
      set({ status: "error", error: toAppError(e) });
    }
  },
  setCapError(capError) {
    set({ capError });
  },
}));

/** True when a refusal is the lifetime image limit (not a daily cap). */
export function isImagesCap(err: AppError | null | undefined): boolean {
  return err?.code === "CAP_REACHED" && (err.details as { scope?: unknown } | undefined)?.scope === "visitor_images";
}

/** The visitor's lifetime images; `out` once none are left (from the limits, or a refusal seen since). */
export function useImages(): { quota: ImageQuota | null; out: boolean } {
  const quota = useLimits((s) => s.data?.images ?? null);
  const capError = useLimits((s) => s.capError);
  const out = (quota?.left !== null && quota?.left !== undefined && quota.left <= 0) || isImagesCap(capError);
  return { quota, out };
}

/** Capped: either the limits say so, or the last POST was refused by a daily cap. */
export function useCapped(): { capped: boolean; resetsAt: string | null } {
  const data = useLimits((s) => s.data);
  const capError = useLimits((s) => s.capError);
  const capped = data?.liveRuns === "capped" || (Boolean(capError) && !isImagesCap(capError));
  const fromErr = (capError?.details as { resetsAt?: string } | undefined)?.resetsAt ?? null;
  return { capped, resetsAt: fromErr ?? data?.dailyTotal.resetsAt ?? null };
}
