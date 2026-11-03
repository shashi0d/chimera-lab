import { Background, Controls, Position as FlowPosition, ReactFlow, useNodesInitialized, useNodesState, useReactFlow, type Edge, type Node } from "@xyflow/react";
import { useEffect, useMemo, useState } from "react";
import { absoluteUrl, baseHeaders } from "../api/client";

export type StudioVersion = { id: string; parentId: string | null; imageUrl: string; instruction: string; direction: string; createdAt: string; mode: string; isFinal?: boolean; sources?: { name: string; hasImage: boolean }[] };
type Position = { x: number; y: number };
const POSITIONS = "chimera.studio.positions.v1";

function positions(): Record<string, Position> {
  try { return JSON.parse(localStorage.getItem(POSITIONS) || "{}"); } catch { return {}; }
}

function ReferenceImage({ versionId, index, name }: { versionId: string; index: number; name: string }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false, objectUrl: string | null = null;
    void fetch(absoluteUrl(`/evo/studio/versions/${encodeURIComponent(versionId)}/sources/${index}`), { headers: baseHeaders() })
      .then((response) => { if (!response.ok) throw new Error("Reference unavailable"); return response.blob(); })
      .then((blob) => { if (!cancelled) { objectUrl = URL.createObjectURL(blob); setUrl(objectUrl); } }).catch(() => {});
    return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [versionId, index]);
  return url ? <img src={url} alt={`${name} reference`} /> : <span className="studio-canvas__reference-placeholder">Reference image</span>;
}

export function StudioCanvas({ versions, selected, onSelect }: { versions: StudioVersion[]; selected: string | null; onSelect: (id: string) => void }) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const initialized = useNodesInitialized();
  const flow = useReactFlow();
  const edges = useMemo<Edge[]>(() => {
    const branches: Edge[] = versions.filter((v) => v.parentId && versions.some((p) => p.id === v.parentId))
      .map((v) => ({ id: `${v.parentId}-${v.id}`, source: v.parentId!, target: v.id, type: "smoothstep" }));
    const sources: Edge[] = versions.filter((v) => !v.parentId).flatMap((v) => ["brief", ...(v.sources ?? []).map((_, i) => `source${i + 1}`)]
      .map((id) => ({ id: `${v.id}-${id}`, source: `${v.id}:${id}`, target: v.id, type: "smoothstep" })));
    return [...branches, ...sources];
  }, [versions]);

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
    const rootOf = (v: StudioVersion): string => {
      let node = v; const seen = new Set<string>();
      while (node.parentId && !seen.has(node.parentId)) {
        seen.add(node.parentId);
        const parent = versions.find((item) => item.id === node.parentId);
        if (!parent) break;
        node = parent;
      }
      return node.id;
    };
    const roots = versions.filter((v) => !v.parentId);
    const rowByGroup: Record<string, number> = {};
    const imageNodes: Node[] = versions.map((v, i) => {
      const column = depth(v);
      const root = rootOf(v), group = Math.max(0, roots.findIndex((item) => item.id === root));
      const slot = `${root}:${column}`, row = rowByGroup[slot] ?? 0;
      rowByGroup[slot] = row + 1;
      return { id: v.id, position: saved[v.id] ?? { x: column * 270, y: group * 1100 + row * 280 }, sourcePosition: FlowPosition.Right, targetPosition: FlowPosition.Left,
        selected: v.id === selected,
        data: { label: <div className="studio-canvas__card"><img src={absoluteUrl(v.imageUrl)} alt="" />
          <strong>Version {i + 1}{v.isFinal ? " · Final choice" : ""}</strong><span>{v.parentId ? "Revision" : "Concept"}</span></div> } };
    });
    const sourceNodes: Node[] = roots.flatMap((v, group) => {
      const items = [{ id: "brief", title: "Creative brief", detail: v.instruction, image: false },
        ...(v.sources ?? []).map((source, index) => ({ id: `source${index + 1}`, title: `Animal ${index + 1}`, detail: source.name, image: source.hasImage }))];
      return items.map((item, index) => ({ id: `${v.id}:${item.id}`, position: saved[`${v.id}:${item.id}`] ?? { x: -270, y: group * 1100 + (index - 1) * 270 },
        sourcePosition: FlowPosition.Right, targetPosition: FlowPosition.Left,
        data: { label: <div className="studio-canvas__source"><span>{item.title}</span>
          {item.image && <ReferenceImage versionId={v.id} index={index} name={item.detail} />}<strong>{item.detail}</strong></div> } }));
    });
    setNodes([...sourceNodes, ...imageNodes]);
  }, [versions, selected, setNodes]);
  useEffect(() => {
    if (initialized && nodes.length > 0) void flow.fitView({ padding: 0.2, maxZoom: 1 });
    // Reframe when the set of image nodes changes, not when the user selects or drags one.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialized, versions.length]);

  return <div className="studio-canvas" aria-label="Connected versions canvas">
    <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onNodeClick={(_event, node) => { if (versions.some((v) => v.id === node.id)) onSelect(node.id); }}
      onNodeDragStop={(_event, node) => { const all = positions(); all[node.id] = node.position; try { localStorage.setItem(POSITIONS, JSON.stringify(all)); } catch { /* optional */ } }}
      fitView minZoom={0.25} maxZoom={1.7} nodesConnectable={false} deleteKeyCode={null}>
      <Background /><Controls showInteractive={false} />
    </ReactFlow>
  </div>;
}
