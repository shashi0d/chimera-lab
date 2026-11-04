import { createStore, get, set } from "idb-keyval";
import { create } from "zustand";
import { copy } from "../copy";
import { GraphLoadError, loadGraph } from "../graph/migrate";
import { useGraph } from "../graph/store";
import type { GraphDoc } from "../graph/types";
import { labApi } from "../lab/api";
import { getDefinition } from "../nodes/registry";
import { toast } from "../ui/toastStore";

/**
 * Each workspace's canvas belongs to the signed-in user and is saved to the server (PUT /evo/lab/workspaces/<id>),
 * so it follows them to another device. A copy per workspace stays in IndexedDB: it is used when the server can't be
 * reached, and is uploaded the next time a save goes through. Photos stay on the device where they were added.
 */

const LOCAL_DEBOUNCE_MS = 500;
const SERVER_DEBOUNCE_MS = 1500;
const SERVER_MAX_WAIT_MS = 6000;

let store: ReturnType<typeof createStore> | null = null;
function db() {
  store ??= createStore("chimera-lab", "graphs");
  return store;
}
const localKey = (userId: string, workspaceId: string) => (workspaceId === "main" ? `graph:${userId}` : `graph:${userId}:${workspaceId}`);

/** Save now (the Save button); resolves when the server has the canvas, or it was kept on this device. */
let flushNow: (() => Promise<void>) | null = null;
export async function saveNow(): Promise<void> {
  await flushNow?.();
}

export type SaveState = "idle" | "saving" | "saved" | "saved-local";

export const useSaveState = create<{ state: SaveState; set(s: SaveState): void }>()((setState) => ({
  state: "idle",
  set: (state) => setState({ state }),
}));

function load(raw: unknown): boolean {
  try {
    const report = loadGraph(raw, (type) => {
      const def = getDefinition(type);
      return def ? { version: def.version, migrate: def.migrate } : undefined;
    });
    useGraph.getState().load(report.graph, { readOnly: report.readOnly });
    if (report.orphanEdgesRemoved) toast.info(copy.graph.orphansRemoved(report.orphanEdgesRemoved));
    return true;
  } catch (e) {
    if (!(e instanceof GraphLoadError)) console.error(e);
    toast.warning(copy.graph.restoredCorrupt);
    return false;
  }
}

/** The user's canvas: from the server, else this device's copy (offline), else empty. */
export async function restoreWorkspace(userId: string, workspaceId: string): Promise<void> {
  useGraph.getState().reset();
  let local: unknown;
  try {
    local = await get(localKey(userId, workspaceId), db());
  } catch {
    local = undefined;
  }
  try {
    const remote = await labApi.loadWorkspace(workspaceId);
    if (remote.graph) {
      load(remote.graph);
      return;
    }
    if (local !== undefined) load(local); // first sign-in on this device after working offline
  } catch {
    if (local !== undefined && load(local)) toast.info("Working offline: changes are kept on this device until the server is reachable.");
  }
}

/** Save every change: to this device at once, to the server a moment later (and before the page hides). */
export function startAutosave(userId: string, workspaceId: string): () => void {
  let localTimer: ReturnType<typeof setTimeout> | null = null;
  let serverTimer: ReturnType<typeof setTimeout> | null = null;
  let firstPendingAt: number | null = null;
  let inflight: Promise<void> | null = null;
  let dirty = false;

  const saveLocal = () => {
    localTimer = null;
    void set(localKey(userId, workspaceId), useGraph.getState().toDoc(), db()).catch(() => undefined);
  };

  const saveServer = async (): Promise<void> => {
    serverTimer = null;
    firstPendingAt = null;
    if (inflight) {
      dirty = true;
      return;
    }
    const doc: GraphDoc = useGraph.getState().toDoc();
    dirty = false;
    useSaveState.getState().set("saving");
    inflight = labApi
      .saveWorkspace(workspaceId, { graph: doc })
      .then(() => useSaveState.getState().set("saved"))
      .catch(() => useSaveState.getState().set("saved-local"))
      .finally(() => {
        inflight = null;
        if (dirty) void saveServer();
      });
    return inflight;
  };

  const unsub = useGraph.subscribe((s, prev) => {
    if (s.revision === prev.revision || s.readOnly) return;
    if (localTimer) clearTimeout(localTimer);
    localTimer = setTimeout(saveLocal, LOCAL_DEBOUNCE_MS);
    const now = Date.now();
    firstPendingAt ??= now;
    if (serverTimer) clearTimeout(serverTimer);
    serverTimer = setTimeout(() => void saveServer(), Math.max(0, Math.min(SERVER_DEBOUNCE_MS, firstPendingAt + SERVER_MAX_WAIT_MS - now)));
  });

  const flush = () => {
    if (localTimer) {
      clearTimeout(localTimer);
      saveLocal();
    }
    if (serverTimer) {
      clearTimeout(serverTimer);
      void saveServer();
    }
  };
  window.addEventListener("pagehide", flush);
  flushNow = async () => {
    if (localTimer) clearTimeout(localTimer);
    saveLocal();
    if (serverTimer) clearTimeout(serverTimer);
    serverTimer = null;
    await saveServer();
    await inflight;
  };
  return () => {
    unsub();
    window.removeEventListener("pagehide", flush);
    flush();
    flushNow = null;
  };
}
