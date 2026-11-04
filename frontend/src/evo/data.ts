import { useEffect } from "react";
import { create } from "zustand";
import { toAppError, type AppError } from "../api/errors";
import { evo } from "./index";
import type { Creature, GalleryItem, Limits } from "./types";

// Read-only API data: limits, gallery, creatures. Small stores so every screen shares one fetch.

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

// ------------------------------------------------------------------ gallery

interface GalleryState extends Load<GalleryItem[]> {
  nextCursor: string | null;
  loadingMore: boolean;
  load(): Promise<void>;
  more(): Promise<void>;
}

export const useGallery = create<GalleryState>()((set, get) => ({
  ...idle<GalleryItem[]>(),
  nextCursor: null,
  loadingMore: false,
  async load() {
    set({ status: "loading", error: null });
    try {
      const page = await evo().getGallery(null);
      set({ status: "ready", data: page.items, nextCursor: page.nextCursor });
    } catch (e) {
      set({ status: "error", error: toAppError(e) });
    }
  },
  async more() {
    const cursor = get().nextCursor;
    if (!cursor || get().loadingMore) return;
    set({ loadingMore: true });
    try {
      const page = await evo().getGallery(cursor);
      set((s) => ({ data: [...(s.data ?? []), ...page.items], nextCursor: page.nextCursor, loadingMore: false }));
    } catch (e) {
      set({ loadingMore: false, error: toAppError(e) });
    }
  },
}));

// ------------------------------------------------------------------ creatures

interface CreaturesState {
  byId: Record<string, Load<Creature>>;
  load(id: string, force?: boolean): Promise<void>;
}

export const useCreatures = create<CreaturesState>()((set, get) => ({
  byId: {},
  async load(id, force = false) {
    const cur = get().byId[id];
    if (!force && cur && (cur.status === "ready" || cur.status === "loading")) return;
    set((s) => ({ byId: { ...s.byId, [id]: { status: "loading", data: cur?.data ?? null, error: null } } }));
    try {
      const data = await evo().getCreature(id);
      set((s) => ({ byId: { ...s.byId, [id]: { status: "ready", data, error: null } } }));
    } catch (e) {
      set((s) => ({ byId: { ...s.byId, [id]: { status: "error", data: null, error: toAppError(e) } } }));
    }
  },
}));

export function useCreature(id: string | null | undefined): Load<Creature> & { reload(): void } {
  const entry = useCreatures((s) => (id ? s.byId[id] : undefined));
  const load = useCreatures((s) => s.load);
  useEffect(() => {
    if (id) void load(id);
  }, [id, load]);
  return { ...(entry ?? idle<Creature>()), reload: () => id && void load(id, true) };
}
