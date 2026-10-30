import { useReactFlow } from "@xyflow/react";
import { useEffect } from "react";
import { copy } from "../copy";
import { useGraph } from "../graph/store";
import { createNode, nodeRegistry } from "../nodes/registry";
import { IconButton } from "../ui/Button";
import { useUi } from "../ui/uiStore";
import { pickImages } from "./filePicker";

const t = copy.toolbar;

export function ToolRail({ onAddFiles }: { onAddFiles: (files: File[]) => void }) {
  const flow = useReactFlow();
  const canUndo = useGraph((s) => s.past.length > 0 && !s.readOnly);
  const canRedo = useGraph((s) => s.future.length > 0 && !s.readOnly);
  const readOnly = useGraph((s) => s.readOnly);
  const minimap = useUi((s) => s.minimap);
  const toggleMinimap = useUi((s) => s.toggleMinimap);

  const addImage = async () => onAddFiles(await pickImages(true));

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "o") {
        e.preventDefault();
        void addImage();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const addNodeOfType = (type: string) => {
    const center = flow.screenToFlowPosition({ x: window.innerWidth / 2, y: window.innerHeight / 2 });
    const node = createNode(type, { x: center.x - 140, y: center.y - 120 });
    useGraph.getState().addNode(node, { select: true });
  };

  return (
    <nav className="tool-rail" aria-label={t.label}>
      <IconButton variant="tool" icon="image" label={t.addImage} onClick={addImage} disabled={readOnly} />
      {Object.values(nodeRegistry)
        .filter((d) => d.addable)
        .map((d) => (
          <IconButton key={d.type} variant="tool" icon={d.icon} label={`Add ${d.label.toLowerCase()} node`} onClick={() => addNodeOfType(d.type)} disabled={readOnly} />
        ))}
      <span className="tool-rail__sep" aria-hidden="true" />
      <IconButton variant="tool" icon="undo" label={t.undo} onClick={() => useGraph.getState().undo()} disabled={!canUndo} />
      <IconButton variant="tool" icon="redo" label={t.redo} onClick={() => useGraph.getState().redo()} disabled={!canRedo} />
      <span className="tool-rail__sep" aria-hidden="true" />
      <IconButton variant="tool" icon="fit" label={t.fitView} onClick={() => void flow.fitView({ padding: 0.2, duration: 250 })} />
      <IconButton variant="tool" icon="map" label={minimap ? t.minimapHide : t.minimapShow} pressed={minimap} onClick={toggleMinimap} />
    </nav>
  );
}
