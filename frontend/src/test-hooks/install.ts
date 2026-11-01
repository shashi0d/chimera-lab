// Test-only hooks (loaded only when import.meta.env.MODE === "test"). Lets the
// screenshot and e2e scripts reach every state without manual clicking.
import { useConnectivity, type ConnectivityStatus } from "../connectivity/store";
import { useLimits } from "../evo/data";
import { evo } from "../evo/index";
import { derived, useEvoRuns, type DerivedRun } from "../evo/runs";
import { loadGraph } from "../graph/migrate";
import { useGraph } from "../graph/store";
import type { GraphDoc } from "../graph/types";
import { getDefinition } from "../nodes/registry";
import { writeRawAutosave } from "../persistence/autosave";
import { useToasts } from "../ui/toastStore";
import { useUi } from "../ui/uiStore";
import { appCrashSignal } from "./signal";

export interface ChimeraTestApi {
  force(status: ConnectivityStatus | null): void;
  crashNode(id: string): void;
  crashApp(): void;
  loadGraph(raw: unknown): void;
  writeAutosave(raw: unknown): Promise<void>;
  clearToasts(): void;
  graph(): GraphDoc;
  runs(): Record<string, DerivedRun>;
  transport(): "http" | "mock";
  /** Mock transport controls (no-ops with the http transport). */
  mock: {
    scenario(s: string): Promise<void>;
    stepMs(ms: number): Promise<void>;
    holdAt(id: number | null): Promise<void>;
    reset(): Promise<void>;
  };
}

async function mockModule() {
  return evo().kind === "mock" ? import("../evo/mock") : null;
}

export function install(): void {
  const api: ChimeraTestApi = {
    force: (s) => useConnectivity.getState().force(s),
    crashNode: (id) => useUi.setState((s) => ({ crashNodes: [...s.crashNodes, id] })),
    crashApp: () => appCrashSignal.trigger(),
    loadGraph: (raw) => {
      const r = loadGraph(raw, (type) => {
        const def = getDefinition(type);
        return def ? { version: def.version, migrate: def.migrate } : undefined;
      });
      useGraph.getState().load(r.graph, { readOnly: r.readOnly });
    },
    writeAutosave: (raw) => writeRawAutosave(raw),
    clearToasts: () => useToasts.setState({ toasts: [] }),
    graph: () => useGraph.getState().toDoc(),
    runs: () => Object.fromEntries(Object.entries(useEvoRuns.getState().runs).map(([k, r]) => [k, derived(r)!])),
    transport: () => evo().kind,
    mock: {
      async scenario(s) {
        const m = await mockModule();
        if (m && m.isMockScenario(s)) {
          m.mockConfig.scenario = s;
          await useLimits.getState().refresh();
        }
      },
      async stepMs(ms) {
        const m = await mockModule();
        if (m) m.mockConfig.stepMs = ms;
      },
      async holdAt(id) {
        const m = await mockModule();
        if (m) m.mockConfig.holdAt = id;
      },
      async reset() {
        const m = await mockModule();
        m?.resetMock();
        useLimits.getState().setCapError(null);
        await useLimits.getState().refresh();
      },
    },
  };
  (window as unknown as { __chimera: ChimeraTestApi }).__chimera = api;
  const params = new URLSearchParams(window.location.search);
  if (params.get("offline") === "1") api.force("offline");
}
