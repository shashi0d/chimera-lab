import { Background, Controls, Position as FlowPosition, ReactFlow, useNodesInitialized, useNodesState, useReactFlow, type Edge, type Node } from "@xyflow/react";
import { useEffect, useMemo } from "react";
import { absoluteUrl } from "../api/client";

export type StudioVersion = { id: string; parentId: string | null; imageUrl: string; instruction: string; direction: string; createdAt: string; mode: string; isFinal?: boolean };
type Position = { x: number; y: number };
const POSITIONS = "chimera.studio.positions.v1";

function positions(): Record<string, Position> {
  try { return JSON.parse(localStorage.getItem(POSITIONS) || "{}"); } catch { return {}; }
}

export function StudioCanvas({ versions, selected, onSelect }: { versions: StudioVersion[]; selected: string | null; onSelect: (id: string) => void }) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const initialized = useNodesInitialized();
  const flow = useReactFlow();
  const edges = useMemo<Edge[]>(() => versions.filter((v) => v.parentId && versions.some((p) => p.id === v.parentId))
    .map((v) => ({ id: `${v.parentId}-${v.id}`, source: v.parentId!, target: v.id, type: "smoothstep" })), [versions]);

  useEffect(() => {
    const saved = positions();
    const depth = (v: StudioVersion): number => {
      let parent = v.parentId, n = 0;
      const seen = new Set<string>();
      while (parent && !seen.has(parent) && n < 100) {
        seen.add(parent); n++;
        parent = versions.find((item) => item.id === parent)?.parentId ?? null;
      }
      return n;
    };
    const rowByDepth: Record<number, number> = {};
    setNodes(versions.map((v, i) => {
      const column = depth(v);
      const row = rowByDepth[column] ?? 0;
      rowByDepth[column] = row + 1;
      return { id: v.id, position: saved[v.id] ?? { x: column * 270, y: row * 280 }, sourcePosition: FlowPosition.Right, targetPosition: FlowPosition.Left,
        selected: v.id === selected,
        data: { label: <div className="studio-canvas__card"><img src={absoluteUrl(v.imageUrl)} alt="" />
          <strong>Version {i + 1}{v.isFinal ? " · Final choice" : ""}</strong><span>{v.parentId ? "Revision" : "Concept"}</span></div> } };
    }));
  }, [versions, selected, setNodes]);
  useEffect(() => {
    if (initialized && nodes.length === versions.length && nodes.length > 0) void flow.fitView({ padding: 0.2, maxZoom: 1 });
    // Reframe when the set of image nodes changes, not when the user selects or drags one.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialized, versions.length]);

  return <div className="studio-canvas" aria-label="Connected versions canvas">
    <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onNodeClick={(_event, node) => onSelect(node.id)}
      onNodeDragStop={(_event, node) => { const all = positions(); all[node.id] = node.position; try { localStorage.setItem(POSITIONS, JSON.stringify(all)); } catch { /* optional */ } }}
      fitView minZoom={0.25} maxZoom={1.7} nodesConnectable={false} deleteKeyCode={null}>
      <Background /><Controls showInteractive={false} />
    </ReactFlow>
  </div>;
}
