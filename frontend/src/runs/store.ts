import { create } from "zustand";
import { api } from "../api/client";
import { toAppError, type AppError } from "../api/errors";
import { uuid } from "../api/session";
import { useGraph } from "../graph/store";
import type { Run } from "../types/api";
import { pollingTransport, TERMINAL, type RunSubscription, type RunTransport } from "./transport";

/** Fields every runnable node keeps in its data (convention shared with the registry). */
export interface RunnableData extends Record<string, unknown> {
  activeRunId?: string | null;
  runIds?: string[];
  stale?: boolean;
}

type RunListener = (nodeId: string, run: Run) => void;

interface RunsState {
  runs: Record<string, Run>;
  /** Errors starting or polling a run, by node id (not run failures). */
  startErrors: Record<string, AppError | undefined>;
  starting: Record<string, boolean>;
  transport: RunTransport;
  start(nodeId: string): Promise<Run | null>;
  cancel(nodeId: string): Promise<void>;
  resume(nodeId: string, runId: string): void;
  upsert(run: Run): void;
  clearStartError(nodeId: string): void;
  setTransport(t: RunTransport): void;
}

const subs = new Map<string, RunSubscription>();
const listeners = new Set<RunListener>();

/** Node types react to run updates (e.g. Fusion creates the Result node). */
export function onRunUpdate(fn: RunListener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function setNodeRun(nodeId: string, runId: string | null): void {
  useGraph.getState().updateNodeData<RunnableData>(nodeId, (d) => ({
    ...d,
    activeRunId: runId,
    runIds: runId && !(d.runIds ?? []).includes(runId) ? [...(d.runIds ?? []), runId] : d.runIds ?? [],
  }));
}

export const useRuns = create<RunsState>()((set, get) => {
  const watch = (nodeId: string, runId: string) => {
    subs.get(runId)?.stop();
    const sub = get().transport.watch(
      runId,
      (run) => {
        get().upsert(run);
        listeners.forEach((fn) => fn(nodeId, run));
        if (TERMINAL.has(run.status)) subs.delete(runId);
      },
      (err) => set((s) => ({ startErrors: { ...s.startErrors, [nodeId]: err } })),
    );
    subs.set(runId, sub);
  };

  return {
    runs: {},
    startErrors: {},
    starting: {},
    transport: pollingTransport,

    upsert(run) {
      set((s) => {
        const prev = s.runs[run.id];
        if (prev && prev.version > run.version) return s;
        return { runs: { ...s.runs, [run.id]: run } };
      });
    },

    async start(nodeId) {
      if (get().starting[nodeId]) return null; // double-click guard
      const node = useGraph.getState().nodes.find((n) => n.id === nodeId);
      const activeId = (node?.data as RunnableData | undefined)?.activeRunId;
      const active = activeId ? get().runs[activeId] : undefined;
      if (active && !TERMINAL.has(active.status)) return null;
      set((s) => ({ starting: { ...s.starting, [nodeId]: true }, startErrors: { ...s.startErrors, [nodeId]: undefined } }));
      try {
        const run = await api.startRun({ graph: useGraph.getState().toDoc(), nodeId }, uuid());
        get().upsert(run);
        setNodeRun(nodeId, run.id);
        listeners.forEach((fn) => fn(nodeId, run));
        watch(nodeId, run.id);
        return run;
      } catch (e) {
        set((s) => ({ startErrors: { ...s.startErrors, [nodeId]: toAppError(e) } }));
        return null;
      } finally {
        set((s) => ({ starting: { ...s.starting, [nodeId]: false } }));
      }
    },

    async cancel(nodeId) {
      const node = useGraph.getState().nodes.find((n) => n.id === nodeId);
      const runId = (node?.data as RunnableData | undefined)?.activeRunId;
      if (!runId) return;
      try {
        const run = await api.cancelRun(runId);
        get().upsert(run);
        listeners.forEach((fn) => fn(nodeId, run));
        subs.get(runId)?.stop();
        subs.delete(runId);
      } catch (e) {
        set((s) => ({ startErrors: { ...s.startErrors, [nodeId]: toAppError(e) } }));
      }
    },

    resume(nodeId, runId) {
      if (subs.has(runId)) return;
      const known = get().runs[runId];
      if (known && TERMINAL.has(known.status)) return;
      watch(nodeId, runId);
    },

    clearStartError(nodeId) {
      set((s) => ({ startErrors: { ...s.startErrors, [nodeId]: undefined } }));
    },

    setTransport(transport) {
      set({ transport });
    },
  };
});

/** After a reload: re-attach to every runnable node's last run (fetches its final state too). */
export function resumeAllRuns(): void {
  for (const n of useGraph.getState().nodes) {
    const runId = (n.data as RunnableData).activeRunId;
    if (runId) useRuns.getState().resume(n.id, runId);
  }
}

export function stopAllRuns(): void {
  subs.forEach((s) => s.stop());
  subs.clear();
}
