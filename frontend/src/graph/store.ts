import { create } from "zustand";
import { uuid } from "../api/session";
import { downstreamIds } from "./queries";
import { CURRENT_SCHEMA_VERSION, type GraphDoc, type GraphEdge, type GraphNode, type NodeData, type Position } from "./types";

const HISTORY_LIMIT = 100;

interface Snapshot {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GraphState {
  graphId: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  selection: string[];
  readOnly: boolean;
  past: Snapshot[];
  future: Snapshot[];
  /** Bumps on every change that should be saved. */
  revision: number;

  load(doc: GraphDoc, opts?: { readOnly?: boolean }): void;
  reset(): void;
  addNode(node: GraphNode, opts?: { select?: boolean }): void;
  addNodes(nodes: GraphNode[], edges?: GraphEdge[]): void;
  removeNodes(ids: string[]): void;
  moveNode(id: string, position: Position, opts?: { commit?: boolean }): void;
  /** Data updates (upload progress, run ids) are not undo steps unless asked. */
  updateNodeData<D extends NodeData>(id: string, updater: (data: D) => D, opts?: { history?: boolean }): void;
  addEdge(edge: Omit<GraphEdge, "id"> & { id?: string }): GraphEdge;
  removeEdges(ids: string[]): void;
  setSelection(ids: string[]): void;
  markDownstreamStale(id: string): void;
  /** Push the current state as an undo point (call before a user action). */
  checkpoint(): void;
  undo(): void;
  redo(): void;
  toDoc(): GraphDoc;
}

function snapshot(s: Pick<GraphState, "nodes" | "edges">): Snapshot {
  return { nodes: s.nodes, edges: s.edges };
}

/**
 * Undo/redo restores structure, positions and config. Nodes that still exist keep
 * their *current* data, so undoing a move never rewinds an upload or a run.
 */
function restore(current: GraphNode[], target: GraphNode[]): GraphNode[] {
  const byId = new Map(current.map((n) => [n.id, n]));
  return target.map((n) => {
    const live = byId.get(n.id);
    return live ? { ...n, data: live.data } : n;
  });
}

function emptyGraph(): Pick<GraphState, "graphId" | "nodes" | "edges" | "selection" | "readOnly" | "past" | "future"> {
  return { graphId: uuid(), nodes: [], edges: [], selection: [], readOnly: false, past: [], future: [] };
}

export const useGraph = create<GraphState>()((set, get) => {
  /** Apply a structural change as one undo step. */
  const commit = (fn: (s: GraphState) => Partial<GraphState>) => {
    const s = get();
    if (s.readOnly) return;
    const past = [...s.past, snapshot(s)].slice(-HISTORY_LIMIT);
    set({ ...fn(s), past, future: [], revision: s.revision + 1 });
  };

  return {
    ...emptyGraph(),
    revision: 0,

    load(doc, opts) {
      set({
        graphId: doc.graphId,
        nodes: doc.nodes,
        edges: doc.edges,
        selection: [],
        readOnly: Boolean(opts?.readOnly),
        past: [],
        future: [],
        revision: get().revision + 1,
      });
    },

    reset() {
      set({ ...emptyGraph(), revision: get().revision + 1 });
    },

    addNode(node, opts) {
      commit((s) => ({ nodes: [...s.nodes, node], selection: opts?.select ? [node.id] : s.selection }));
    },

    addNodes(nodes, edges = []) {
      commit((s) => ({ nodes: [...s.nodes, ...nodes], edges: [...s.edges, ...edges] }));
    },

    removeNodes(ids) {
      if (!ids.length) return;
      const drop = new Set(ids);
      commit((s) => ({
        nodes: s.nodes.filter((n) => !drop.has(n.id)),
        edges: s.edges.filter((e) => !drop.has(e.source) && !drop.has(e.target)),
        selection: s.selection.filter((id) => !drop.has(id)),
      }));
    },

    moveNode(id, position, opts) {
      const s = get();
      if (s.readOnly) return;
      const apply = (st: GraphState) => ({ nodes: st.nodes.map((n) => (n.id === id ? { ...n, position } : n)) });
      if (opts?.commit) commit(apply);
      else set({ ...apply(s), revision: s.revision + 1 });
    },

    updateNodeData(id, updater, opts) {
      const apply = (st: GraphState) => ({
        nodes: st.nodes.map((n) => (n.id === id ? { ...n, data: updater(n.data as never) } : n)),
      });
      if (opts?.history) commit(apply);
      else set((st) => ({ ...apply(st), revision: st.revision + 1 }));
    },

    addEdge(partial) {
      const edge: GraphEdge = { ...partial, id: partial.id ?? `e-${uuid().slice(0, 8)}` };
      commit((s) => ({ edges: [...s.edges, edge] }));
      return edge;
    },

    removeEdges(ids) {
      if (!ids.length) return;
      const drop = new Set(ids);
      commit((s) => ({ edges: s.edges.filter((e) => !drop.has(e.id)), selection: s.selection.filter((x) => !drop.has(x)) }));
    },

    setSelection(ids) {
      set({ selection: ids });
    },

    markDownstreamStale(id) {
      const targets = new Set(downstreamIds(get(), id));
      if (!targets.size) return;
      set((s) => ({
        nodes: s.nodes.map((n) => (targets.has(n.id) && hasResult(n) ? { ...n, data: { ...n.data, stale: true } } : n)),
        revision: s.revision + 1,
      }));
    },

    checkpoint() {
      const s = get();
      set({ past: [...s.past, snapshot(s)].slice(-HISTORY_LIMIT), future: [] });
    },

    undo() {
      const s = get();
      const prev = s.past[s.past.length - 1];
      if (!prev || s.readOnly) return;
      set({
        nodes: restore(s.nodes, prev.nodes),
        edges: prev.edges,
        past: s.past.slice(0, -1),
        future: [snapshot(s), ...s.future].slice(0, HISTORY_LIMIT),
        selection: [],
        revision: s.revision + 1,
      });
    },

    redo() {
      const s = get();
      const next = s.future[0];
      if (!next || s.readOnly) return;
      set({
        nodes: restore(s.nodes, next.nodes),
        edges: next.edges,
        past: [...s.past, snapshot(s)].slice(-HISTORY_LIMIT),
        future: s.future.slice(1),
        selection: [],
        revision: s.revision + 1,
      });
    },

    toDoc() {
      const s = get();
      return { schemaVersion: CURRENT_SCHEMA_VERSION, graphId: s.graphId, nodes: s.nodes, edges: s.edges };
    },
  };
});

/** Only nodes that hold a produced result can go stale. */
function hasResult(n: GraphNode): boolean {
  const d = n.data;
  return Boolean(d.activeRunId || (Array.isArray(d.versions) && d.versions.length) || (Array.isArray(d.runIds) && d.runIds.length));
}
