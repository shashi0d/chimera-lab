import { createStore, del, get, set } from "idb-keyval";
import { create } from "zustand";
import { api } from "../api/client";
import { useConnectivity } from "../connectivity/store";
import { copy } from "../copy";
import { GraphLoadError, loadGraph } from "../graph/migrate";
import { useGraph } from "../graph/store";
import { getDefinition } from "../nodes/registry";
import { toast } from "../ui/toastStore";

const KEY = "graph:current";
const LOCAL_DEBOUNCE_MS = 500;
const SERVER_DEBOUNCE_MS = 2000;

let store: ReturnType<typeof createStore> | null = null;
function db() {
  store ??= createStore("chimera-lab", "graphs");
  return store;
}

export type SaveState = "idle" | "saving" | "saved-local" | "saved";

export const useSaveState = create<{ state: SaveState; set(s: SaveState): void }>()((setState) => ({
  state: "idle",
  set: (state) => setState({ state }),
}));

/** Restore the autosaved graph. Corrupt saves are discarded with a toast (TASKSHEET 7.6). */
export async function restoreGraph(): Promise<void> {
  let raw: unknown;
  try {
    raw = await get(KEY, db());
  } catch {
    raw = undefined;
  }
  if (raw === undefined) return;
  try {
    const report = loadGraph(raw, (type) => {
      const def = getDefinition(type);
      return def ? { version: def.version, migrate: def.migrate } : undefined;
    });
    useGraph.getState().load(report.graph, { readOnly: report.readOnly });
    if (report.orphanEdgesRemoved) toast.info(copy.graph.orphansRemoved(report.orphanEdgesRemoved));
  } catch (e) {
    if (!(e instanceof GraphLoadError)) console.error(e);
    await del(KEY, db()).catch(() => undefined);
    toast.warning(copy.graph.restoredCorrupt);
  }
}

const LOCAL_MAX_WAIT_MS = 2000;

/**
 * Debounced autosave to IndexedDB (500ms, but never more than 2s behind during a
 * burst such as upload progress) and, when online, to the backend (2s). Pending
 * work is flushed on teardown (e.g. the app error boundary) and on page hide.
 */
export function startAutosave(): () => void {
  let localTimer: ReturnType<typeof setTimeout> | null = null;
  let serverTimer: ReturnType<typeof setTimeout> | null = null;
  let firstPendingAt: number | null = null;

  const saveLocal = () => {
    localTimer = null;
    firstPendingAt = null;
    set(KEY, useGraph.getState().toDoc(), db())
      .then(() => useSaveState.getState().set("saved-local"))
      .catch(() => undefined); // quota or private mode: nothing more we can do locally
  };

  const unsub = useGraph.subscribe((s, prev) => {
    if (s.revision === prev.revision || s.readOnly) return;
    useSaveState.getState().set("saving");
    const now = Date.now();
    firstPendingAt ??= now;
    if (localTimer) clearTimeout(localTimer);
    localTimer = setTimeout(saveLocal, Math.max(0, Math.min(LOCAL_DEBOUNCE_MS, firstPendingAt + LOCAL_MAX_WAIT_MS - now)));
    if (serverTimer) clearTimeout(serverTimer);
    serverTimer = setTimeout(async () => {
      if (useConnectivity.getState().status !== "online") return;
      try {
        await api.saveGraph(useGraph.getState().toDoc());
        useSaveState.getState().set("saved");
      } catch {
        /* stays saved locally; connectivity handles the banner */
      }
    }, SERVER_DEBOUNCE_MS);
  });

  const flush = () => {
    if (localTimer) {
      clearTimeout(localTimer);
      saveLocal();
    }
  };
  window.addEventListener("pagehide", flush);
  return () => {
    unsub();
    window.removeEventListener("pagehide", flush);
    flush();
    if (serverTimer) clearTimeout(serverTimer);
  };
}

/** Test/debug: write raw data as the autosave (used to simulate corrupt or legacy saves). */
export async function writeRawAutosave(raw: unknown): Promise<void> {
  await set(KEY, raw, db());
}
