import { create } from "zustand";
import { navigate } from "../app/route";
import type { NodeConfig, NodeData } from "../graph/types";
import { forgetLocalCanvas } from "../persistence/autosave";
import { useWorkspaces } from "../persistence/workspaces";
import { clearSandbox, DAM, SIRE, STYLE, TUTORIAL_WS } from "./sandbox";

/**
 * The hands-on tutorial. It runs in the real Lab (workspace "tutorial", answered by tutorial/sandbox.ts). Inside the
 * Lab the current step follows what is on the canvas (Tour.tsx); after that come Chimeras, then the workspaces.
 * Finished or skipped once: it never starts by itself again.
 */

const DONE_KEY = "chimera.toured";
const STATE_KEY = "chimera.tour";

export type TourPhase = "lab" | "chimeras" | "workspaces";

export function hasToured(): boolean {
  try {
    return localStorage.getItem(DONE_KEY) === "1";
  } catch {
    return false;
  }
}

function saved(): { active: boolean; phase: TourPhase } {
  try {
    const s = JSON.parse(localStorage.getItem(STATE_KEY) ?? "null") as { active?: boolean; phase?: TourPhase } | null;
    if (s?.active && (s.phase === "lab" || s.phase === "chimeras" || s.phase === "workspaces")) return { active: true, phase: s.phase };
  } catch {
    /* fall through */
  }
  return { active: false, phase: "lab" };
}

function persist(active: boolean, phase: TourPhase): void {
  try {
    if (active) localStorage.setItem(STATE_KEY, JSON.stringify({ active, phase }));
    else localStorage.removeItem(STATE_KEY);
  } catch {
    /* storage blocked: the tour lasts for this page */
  }
}

interface TourState {
  active: boolean;
  phase: TourPhase;
  /** Begin (again) from a clean tutorial workspace. */
  start(): Promise<void>;
  setPhase(phase: TourPhase): void;
  /** Finish (a workspace was created) or skip (back to the workspace list). */
  end(opts?: { skipped?: boolean }): void;
}

async function cleanTutorial(): Promise<void> {
  clearSandbox();
  const userId = useWorkspaces.getState().userId;
  if (userId) await forgetLocalCanvas(userId, TUTORIAL_WS);
}

export const useTour = create<TourState>()((set) => ({
  ...saved(),

  async start() {
    await cleanTutorial();
    persist(true, "lab");
    set({ active: true, phase: "lab" });
    // Leave and re-enter the workspace so its (now empty) canvas loads again.
    if (useWorkspaces.getState().currentId === TUTORIAL_WS) useWorkspaces.setState({ currentId: null });
    useWorkspaces.getState().open(TUTORIAL_WS);
    navigate({ view: "lab", runId: null, workspaceId: TUTORIAL_WS });
  },

  setPhase(phase) {
    persist(true, phase);
    set({ phase });
  },

  end(opts) {
    try {
      localStorage.setItem(DONE_KEY, "1");
    } catch {
      /* it may offer itself again next visit */
    }
    persist(false, "lab");
    set({ active: false, phase: "lab" });
    void cleanTutorial();
    if (opts?.skipped) navigate({ view: "home" });
  },
}));

/** A node added from the toolbar during the tutorial comes prefilled (the Fusion: Tiger + Bat, anime). */
export function tourPrefill(type: string): { data?: NodeData; config?: NodeConfig } | null {
  const s = useTour.getState();
  if (!s.active || s.phase !== "lab" || type !== "fusion" || useWorkspaces.getState().currentId !== TUTORIAL_WS) return null;
  return { data: { names: { a: SIRE, b: DAM } }, config: { style: STYLE } };
}
