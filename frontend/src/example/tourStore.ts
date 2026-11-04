import { create } from "zustand";
import { navigate, type Route } from "../app/route";
import { useGraph } from "../graph/store";
import { EXAMPLE_IDS, EXAMPLE_WS } from "./example";

/** The guided tour through the example workspace. Finished or skipped once: it never opens by itself again. */

const DONE_KEY = "chimera.toured";

export type TourStepId = "fusion" | "image" | "tools" | "card" | "chimeras" | "start";

interface StepSpec {
  id: TourStepId;
  route: Route;
  /** The canvas node selected (and centred) on this step. */
  select?: string;
}

const LAB: Route = { view: "lab", runId: null, workspaceId: EXAMPLE_WS };

export const TOUR_STEPS: readonly StepSpec[] = [
  { id: "fusion", route: LAB, select: EXAMPLE_IDS.fusion },
  { id: "image", route: LAB, select: EXAMPLE_IDS.version },
  { id: "tools", route: LAB, select: EXAMPLE_IDS.version },
  { id: "card", route: LAB, select: EXAMPLE_IDS.card },
  { id: "chimeras", route: { view: "chimeras" } },
  { id: "start", route: { view: "chimeras" } },
];

export function hasToured(): boolean {
  try {
    return localStorage.getItem(DONE_KEY) === "1";
  } catch {
    return false;
  }
}

function markToured(): void {
  try {
    localStorage.setItem(DONE_KEY, "1");
  } catch {
    /* storage blocked: the tour offers itself again next visit */
  }
}

interface TourState {
  active: boolean;
  step: number;
  start(): void;
  go(step: number): void;
  /** Skip or finish: closes the tour and remembers it. */
  end(): void;
}

/** Show a step: its page, and its node selected (the canvas loads the example first, so retry briefly). */
function enter(step: number): void {
  const spec = TOUR_STEPS[step];
  if (!spec) return;
  navigate(spec.route);
  if (!spec.select) return;
  const id = spec.select;
  let tries = 0;
  const pick = () => {
    const g = useGraph.getState();
    if (g.nodes.some((n) => n.id === id)) g.setSelection([id]);
    else if (tries++ < 40) window.setTimeout(pick, 50);
  };
  pick();
}

export const useTour = create<TourState>()((set, get) => ({
  active: false,
  step: 0,
  start() {
    set({ active: true, step: 0 });
    enter(0);
  },
  go(step) {
    if (!get().active || step < 0 || step >= TOUR_STEPS.length) return;
    set({ step });
    enter(step);
  },
  end() {
    markToured();
    set({ active: false, step: 0 });
  },
}));
