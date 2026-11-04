import { create } from "zustand";
import { toAppError, type AppError } from "../api/errors";
import { evo } from "./index";
import type { Limits } from "./types";

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

/** Capped: either the limits say so, or the last POST was refused by a daily cap. */
export function useCapped(): { capped: boolean; resetsAt: string | null } {
  const data = useLimits((s) => s.data);
  const capError = useLimits((s) => s.capError);
  const capped = data?.liveRuns === "capped" || Boolean(capError);
  const fromErr = (capError?.details as { resetsAt?: string } | undefined)?.resetsAt ?? null;
  return { capped, resetsAt: fromErr ?? data?.dailyTotal.resetsAt ?? null };
}
