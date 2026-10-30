// Test-only hooks (loaded only when import.meta.env.MODE === "test"). Lets the
// screenshot and e2e scripts reach every state without manual clicking.
import { apiConfig } from "../api/client";
import { useConnectivity, type ConnectivityStatus } from "../connectivity/store";
import { loadGraph } from "../graph/migrate";
import { useGraph } from "../graph/store";
import type { GraphDoc } from "../graph/types";
import { writeRawAutosave } from "../persistence/autosave";
import { getDefinition } from "../nodes/registry";
import { stopAllRuns, useRuns } from "../runs/store";
import type { RunTransport } from "../runs/transport";
import type { Run } from "../types/api";
import { useToasts } from "../ui/toastStore";
import { useUi } from "../ui/uiStore";
import { appCrashSignal } from "./signal";

const frozen: RunTransport = { watch: () => ({ stop: () => undefined }) };

export interface ChimeraTestApi {
  setFault(fault: string | null): void;
  force(status: ConnectivityStatus | null): void;
  crashNode(id: string): void;
  crashApp(): void;
  loadGraph(raw: unknown): void;
  writeAutosave(raw: unknown): Promise<void>;
  /** Show a synthetic run on a node and stop polling (for "running at step X" shots). */
  setRun(nodeId: string, run: Run): void;
  freezeRuns(): void;
  clearToasts(): void;
  openPanel(nodeId: string): void;
  graph(): GraphDoc;
  runs(): Record<string, Run>;
}

export function install(): void {
  const api: ChimeraTestApi = {
    setFault: (f) => {
      apiConfig.fault = f;
    },
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
    setRun: (nodeId, run) => {
      stopAllRuns();
      useRuns.getState().setTransport(frozen);
      useRuns.getState().upsert(run);
      useGraph.getState().updateNodeData(nodeId, (d) => ({ ...d, activeRunId: run.id }));
    },
    freezeRuns: () => {
      stopAllRuns();
      useRuns.getState().setTransport(frozen);
    },
    clearToasts: () => useToasts.setState({ toasts: [] }),
    openPanel: (id) => useUi.getState().openPanel(id),
    graph: () => useGraph.getState().toDoc(),
    runs: () => useRuns.getState().runs,
  };
  (window as unknown as { __chimera: ChimeraTestApi }).__chimera = api;
  const params = new URLSearchParams(window.location.search);
  if (params.get("fault")) api.setFault(params.get("fault"));
  if (params.get("offline") === "1") api.force("offline");
}
