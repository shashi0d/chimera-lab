import {
  Background,
  BackgroundVariant,
  MiniMap,
  ReactFlow,
  useReactFlow,
  type Connection,
  type Edge,
  type FinalConnectionState,
  type Node,
  type NodeChange,
  type NodeProps,
  type EdgeChange,
} from "@xyflow/react";
import { memo, useCallback, useEffect, useMemo, useRef, useState, type ComponentType, type DragEvent } from "react";
import { useConnectivity } from "../connectivity/store";
import { copy } from "../copy";
import { checkConnection, type ConnectionAttempt, type RefusalReason } from "../graph/edgeRules";
import { useGraph } from "../graph/store";
import type { GraphNode } from "../graph/types";
import { getDefinition, nodeRegistry, portsOf } from "../nodes/registry";
import type { AnyNodeDefinition, ValidationIssue } from "../nodes/types";
import { UnsupportedNodeView } from "../nodes/unsupported/NodeView";
import { derived, isTerminal, useEvoRuns } from "../evo/runs";
import { createNode } from "../nodes/registry";
import { toast } from "../ui/toastStore";
import { useUi } from "../ui/uiStore";
import { addImageFiles, findFreeSpot, FOOTPRINT } from "./addImages";
import { DropMenu, type DropAt } from "./DropMenu";
import { LibraryDialog } from "./LibraryDialog";
import type { LabVersion } from "../lab/api";
import { afterNodesDeleted, confirmImageDelete } from "../lab/deletion";
import { EmptyState } from "./EmptyState";
import { NodeErrorBoundary } from "./NodeErrorBoundary";
import { ToolRail } from "./ToolRail";
import { ZoomControls } from "./ZoomControls";

interface FlowData extends Record<string, unknown> {
  node: GraphNode;
  issues: ValidationIssue[];
  catalog: number;
}
type FlowNode = Node<FlowData>;

function makeNodeComponent(def: AnyNodeDefinition): ComponentType<NodeProps<FlowNode>> {
  const View = def.View;
  const Component = ({ id, data, selected }: NodeProps<FlowNode>) => (
    <NodeErrorBoundary nodeId={id}>
      <View node={data.node} selected={Boolean(selected)} issues={data.issues} catalog={data.catalog} />
    </NodeErrorBoundary>
  );
  Component.displayName = `Node(${def.type})`;
  return memo(Component);
}

const UnsupportedFlowNode = memo(({ data }: NodeProps<FlowNode>) => <UnsupportedNodeView type={data.node.type} catalog={data.catalog} />);

const nodeTypes: Record<string, ComponentType<NodeProps<FlowNode>>> = {
  ...Object.fromEntries(Object.values(nodeRegistry).map((d) => [d.type, makeNodeComponent(d)])),
  unsupported: UnsupportedFlowNode,
};

const REFUSAL_COPY: Record<RefusalReason, string> = {
  self: copy.graph.refusedSelf,
  type: copy.graph.refusedType,
  occupied: copy.graph.refusedOccupied,
  cycle: copy.graph.refusedCycle,
  unknown: copy.graph.refusedType,
};

function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  return Boolean(el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName)));
}

export function Canvas() {
  const nodes = useGraph((s) => s.nodes);
  const edges = useGraph((s) => s.edges);
  const selection = useGraph((s) => s.selection);
  const readOnly = useGraph((s) => s.readOnly);
  const connectivity = useConnectivity((s) => s.status);
  const runs = useEvoRuns((s) => s.runs);
  const minimap = useUi((s) => s.minimap);
  const theme = useUi((s) => s.theme);
  const flow = useReactFlow();
  const wrapper = useRef<HTMLDivElement>(null);
  const [measured, setMeasured] = useState<Record<string, { width: number; height: number }>>({});
  const [dragging, setDragging] = useState(false);
  const [dropAt, setDropAt] = useState<DropAt | null>(null);
  const closeDropMenu = useCallback(() => setDropAt(null), []);
  const [library, setLibrary] = useState(false);
  const closeLibrary = useCallback(() => setLibrary(false), []);
  const addVersionCard = useCallback(
    (v: LabVersion) => {
      const center = flow.screenToFlowPosition({ x: window.innerWidth / 2, y: window.innerHeight / 2 });
      const size = FOOTPRINT.version!;
      const node = createNode("version", findFreeSpot({ x: center.x - size.w / 2, y: center.y - size.h / 2 }, size.w, size.h), { version: v, runId: null, error: null });
      useGraph.getState().addNode(node, { select: true });
    },
    [flow],
  );
  const [shake, setShake] = useState<string | null>(null);

  // ---------------------------------------------------------------- derived flow state

  // Dragging moves one node per frame: every other node keeps its `data` object (same node content, same issues), so
  // its memoised view does not re-render. A node's content is its type, config and data; its position is not.
  const dataCache = useRef(new Map<string, { node: GraphNode; issuesKey: string; data: FlowData }>());
  const flowNodes: FlowNode[] = useMemo(() => {
    const ctx = { graph: { nodes, edges }, connectivity, readOnly };
    const sel = new Set(selection);
    const cache = dataCache.current;
    const seen = new Set<string>();
    const out = nodes.map((n, i) => {
      const def = getDefinition(n.type);
      const issues = def ? def.validate(n, ctx) : [];
      const issuesKey = issues.length ? JSON.stringify(issues) : "";
      const prev = cache.get(n.id);
      const same = prev && prev.issuesKey === issuesKey && prev.data.catalog === i + 1 && prev.node.type === n.type &&
        prev.node.config === n.config && prev.node.data === n.data && prev.node.version === n.version;
      const data = same ? prev.data : { node: n, issues, catalog: i + 1 };
      if (!same) cache.set(n.id, { node: n, issuesKey, data });
      seen.add(n.id);
      return {
        id: n.id,
        type: def ? def.type : "unsupported",
        position: n.position,
        data,
        selected: sel.has(n.id),
        measured: measured[n.id],
        className: shake === n.id ? "is-shaking" : undefined,
        draggable: !readOnly,
        deletable: !readOnly,
        connectable: !readOnly && Boolean(def),
      };
    });
    for (const id of cache.keys()) if (!seen.has(id)) cache.delete(id);
    return out;
  }, [nodes, edges, selection, connectivity, readOnly, measured, shake]);

  const flowEdges: Edge[] = useMemo(() => {
    const sel = new Set(selection);
    const runningTargets = new Set(
      nodes
        .filter((n) => {
          const runId = n.data.activeRunId as string | undefined;
          const run = runId ? derived(runs[runId]) : null;
          return run && !isTerminal(run.status);
        })
        .map((n) => n.id),
    );
    return edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourcePort,
      targetHandle: e.targetPort,
      selected: sel.has(e.id),
      className: runningTargets.has(e.target) || runningTargets.has(e.source) ? "edge--active" : undefined,
      deletable: !readOnly,
    }));
  }, [edges, nodes, runs, selection, readOnly]);

  // ---------------------------------------------------------------- changes from React Flow

  const onNodesChange = useCallback((changes: NodeChange<FlowNode>[]) => {
    const g = useGraph.getState();
    let nextSel: string[] | null = null;
    const dims: Record<string, { width: number; height: number }> = {};
    for (const c of changes) {
      if (c.type === "position" && c.position) g.moveNode(c.id, c.position);
      else if (c.type === "dimensions" && c.dimensions) dims[c.id] = c.dimensions;
      else if (c.type === "select") {
        nextSel ??= [...useGraph.getState().selection];
        nextSel = c.selected ? [...new Set([...nextSel, c.id])] : nextSel.filter((x) => x !== c.id);
      }
    }
    if (Object.keys(dims).length) setMeasured((m) => ({ ...m, ...dims }));
    if (nextSel) g.setSelection(nextSel);
  }, []);

  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    let nextSel: string[] | null = null;
    for (const c of changes) {
      if (c.type === "select") {
        nextSel ??= [...useGraph.getState().selection];
        nextSel = c.selected ? [...new Set([...nextSel, c.id])] : nextSel.filter((x) => x !== c.id);
      }
    }
    if (nextSel) useGraph.getState().setSelection(nextSel);
  }, []);

  const onDelete = useCallback(({ nodes: ns, edges: es }: { nodes: Node[]; edges: Edge[] }) => {
    const g = useGraph.getState();
    if (g.readOnly) return;
    const nodeIds = ns.map((n) => n.id);
    const gone = new Set(nodeIds);
    const edgeIds = es.filter((e) => !gone.has(e.source) && !gone.has(e.target)).map((e) => e.id);
    // one undo step for the whole deletion
    g.checkpoint();
    useGraph.setState((s) => ({
      nodes: s.nodes.filter((n) => !gone.has(n.id)),
      edges: s.edges.filter((e) => !gone.has(e.source) && !gone.has(e.target) && !edgeIds.includes(e.id)),
      selection: [],
      revision: s.revision + 1,
    }));
    afterNodesDeleted();
  }, []);

  // Deleting images is permanent (server and device): ask first.
  const onBeforeDelete = useCallback(async ({ nodes: ns }: { nodes: Node[]; edges: Edge[] }) => {
    if (useGraph.getState().readOnly) return false;
    return confirmImageDelete(ns.map((n) => n.id));
  }, []);

  const attempt = (c: Connection): ConnectionAttempt => ({
    source: c.source,
    sourcePort: c.sourceHandle ?? "out",
    target: c.target,
    targetPort: c.targetHandle ?? "",
  });

  const isValidConnection = useCallback(
    (c: Connection | Edge) => checkConnection(useGraph.getState(), attempt(c as Connection), portsOf).ok,
    [],
  );

  const onConnect = useCallback((c: Connection) => {
    const g = useGraph.getState();
    const a = attempt(c);
    const res = checkConnection(g, a, portsOf);
    if (!res.ok) return;
    g.addEdge(a);
    g.markDownstreamStale(a.source);
  }, []);

  const refuse = useCallback((nodeId: string, reason: RefusalReason) => {
    toast.warning(REFUSAL_COPY[reason]);
    setShake(null);
    requestAnimationFrame(() => setShake(nodeId));
    window.setTimeout(() => setShake((s) => (s === nodeId ? null : s)), 400);
  }, []);

  const onConnectEnd = useCallback(
    (e: MouseEvent | TouchEvent, state: FinalConnectionState) => {
      // FLORA-style: drag from an image's output onto empty canvas, then choose what to make from it there.
      if (!state.toNode && state.fromNode?.type === "version" && state.fromHandle?.type === "source" && !useGraph.getState().readOnly) {
        const point = "changedTouches" in e ? e.changedTouches[0]! : e;
        const screen = { x: point.clientX, y: point.clientY };
        const box = wrapper.current?.getBoundingClientRect() ?? { x: 0, y: 0 };
        setDropAt({ nodeId: state.fromNode.id, local: { x: screen.x - box.x, y: screen.y - box.y }, flow: flow.screenToFlowPosition(screen) });
        return;
      }
      if (state.isValid || !state.toHandle || !state.fromHandle || !state.toNode || !state.fromNode) return;
      const fromIsSource = state.fromHandle.type === "source";
      const c: ConnectionAttempt = fromIsSource
        ? { source: state.fromNode.id, sourcePort: state.fromHandle.id ?? "out", target: state.toNode.id, targetPort: state.toHandle.id ?? "" }
        : { source: state.toNode.id, sourcePort: state.toHandle.id ?? "out", target: state.fromNode.id, targetPort: state.fromHandle.id ?? "" };
      const res = checkConnection(useGraph.getState(), c, portsOf);
      if (!res.ok) refuse(state.toNode.id, res.reason);
    },
    [refuse, flow],
  );

  // ---------------------------------------------------------------- files: drop + paste

  const viewportCenter = useCallback(() => {
    const rect = wrapper.current?.getBoundingClientRect();
    const p = flow.screenToFlowPosition({ x: (rect?.left ?? 0) + (rect?.width ?? 800) / 2, y: (rect?.top ?? 0) + (rect?.height ?? 600) / 2 });
    return { x: p.x - 260, y: p.y - 200 };
  }, [flow]);

  const addFiles = useCallback(
    async (files: File[], at?: { x: number; y: number }) => {
      if (!files.length) return;
      const wasEmpty = useGraph.getState().nodes.length === 0;
      await addImageFiles(files, at ?? viewportCenter());
      if (wasEmpty) requestAnimationFrame(() => void flow.fitView({ padding: 0.25, duration: 300, maxZoom: 1 }));
    },
    [flow, viewportCenter],
  );

  const onDragOver = (e: DragEvent) => {
    if (!e.dataTransfer.types.includes("Files") || readOnly) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
    setDragging(true);
  };
  const onDrop = (e: DragEvent) => {
    if (!e.dataTransfer.files.length) return;
    e.preventDefault();
    setDragging(false);
    const p = flow.screenToFlowPosition({ x: e.clientX, y: e.clientY });
    void addFiles(Array.from(e.dataTransfer.files), { x: p.x - 110, y: p.y - 120 });
  };

  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      if (isTyping(e.target)) return;
      const files = Array.from(e.clipboardData?.files ?? []).filter((f) => f.type.startsWith("image/") || f.type === "");
      if (!files.length) return;
      e.preventDefault();
      void addFiles(files);
    };
    document.addEventListener("paste", onPaste);
    return () => document.removeEventListener("paste", onPaste);
  }, [addFiles]);

  /** No photos: a Fusion node on its own takes two typed names (the contract's name fallback). */
  const addNamesOnly = useCallback(() => {
    const at = viewportCenter();
    const node = createNode("fusion", { x: at.x + 100, y: at.y });
    useGraph.getState().addNode(node, { select: true });
    requestAnimationFrame(() => {
      void flow.fitView({ padding: 0.3, duration: 300, maxZoom: 1 });
      document.querySelector<HTMLInputElement>(`[data-node-id="${CSS.escape(node.id)}"] input`)?.focus();
    });
  }, [flow, viewportCenter]);

  // ---------------------------------------------------------------- keep new nodes in view

  const knownIds = useRef<Set<string> | null>(null);
  useEffect(() => {
    const ids = new Set(nodes.map((n) => n.id));
    const prev = knownIds.current;
    knownIds.current = ids;
    if (!prev || prev.size === 0) return; // first load / empty canvas is handled by fitView
    const added = nodes.filter((n) => !prev.has(n.id));
    if (!added.length) return;
    const rect = wrapper.current?.getBoundingClientRect();
    if (!rect) return;
    const offscreen = added.some((n) => {
      const p = flow.flowToScreenPosition(n.position);
      const size = measured[n.id] ?? { width: FOOTPRINT[n.type]?.w ?? 300, height: FOOTPRINT[n.type]?.h ?? 300 };
      const z = flow.getZoom();
      return p.x < rect.left || p.y < rect.top || p.x + size.width * z > rect.right || p.y + size.height * z > rect.bottom;
    });
    // Zoom out only as far as needed; never zoom in on the user.
    // Wait a beat so React Flow has measured the new nodes before fitting.
    if (offscreen) window.setTimeout(() => void flow.fitView({ padding: 0.15, maxZoom: flow.getZoom(), duration: 300 }), 120);
  }, [nodes, flow, measured]);

  // ---------------------------------------------------------------- keyboard shortcuts

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTyping(e.target)) return;
      const mod = e.metaKey || e.ctrlKey;
      const g = useGraph.getState();
      if (mod && e.key.toLowerCase() === "z") {
        e.preventDefault();
        if (e.shiftKey) g.redo();
        else g.undo();
      } else if (mod && e.key.toLowerCase() === "y") {
        e.preventDefault();
        g.redo();
      } else if (e.shiftKey && (e.key === "!" || e.code === "Digit1")) {
        e.preventDefault();
        void flow.fitView({ padding: 0.2, duration: 250 });
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [flow]);

  return (
    <div
      ref={wrapper}
      className={`canvas${dragging ? " is-drop-target" : ""}`}
      onDragOver={onDragOver}
      onDragLeave={(e) => {
        if (e.currentTarget === e.target) setDragging(false);
      }}
      onDrop={onDrop}
    >
      <ReactFlow<FlowNode>
        nodes={flowNodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onDelete={onDelete}
        onBeforeDelete={onBeforeDelete}
        onConnect={onConnect}
        onConnectEnd={onConnectEnd}
        isValidConnection={isValidConnection}
        onNodeDragStart={() => useGraph.getState().checkpoint()}
        deleteKeyCode={readOnly ? null : ["Delete", "Backspace"]}
        colorMode={theme}
        minZoom={0.2}
        maxZoom={2}
        zoomOnDoubleClick={false}
        onlyRenderVisibleElements
        elevateNodesOnSelect={false}
        fitView
        fitViewOptions={{ padding: 0.25, maxZoom: 1 }}
        proOptions={{ hideAttribution: true }}
        nodesConnectable={!readOnly}
        elementsSelectable
        selectNodesOnDrag={false}
        aria-label={copy.lab.canvasLabel}
      >
        <Background variant={BackgroundVariant.Dots} gap={28} size={1.6} className="canvas__grid" />
        {minimap ? <MiniMap pannable zoomable className="canvas__minimap" ariaLabel="Minimap" /> : null}
      </ReactFlow>
      {dropAt ? (
        <DropMenu at={dropAt} onClose={closeDropMenu} />
      ) : null}
      <ToolRail onAddImage={() => setLibrary(true)} />
      {library ? <LibraryDialog onClose={closeLibrary} onAddFiles={(files) => void addFiles(files)} onAddVersion={addVersionCard} /> : null}
      <ZoomControls />
      {nodes.length === 0 && !dragging ? <EmptyState onAddImage={() => setLibrary(true)} onTypeNames={addNamesOnly} /> : null}
      {dragging ? (
        <div className="drop-overlay" aria-hidden="true">
          <p className="drop-overlay__label">{copy.empty.dropHere}</p>
        </div>
      ) : null}
    </div>
  );
}
