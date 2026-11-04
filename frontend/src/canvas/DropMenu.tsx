import { useEffect, useRef } from "react";
import { addCardNode, addEditNode, addFusionFrom } from "../lab/graph";
import { saveCreature } from "../lab/store";
import type { VersionData } from "../nodes/version/types";
import { useGraph } from "../graph/store";
import { Icon, type IconName } from "../ui/Icon";

/** Where an image's output was dropped on empty canvas: the point inside the canvas element (for the menu) and on
 * the canvas (for the new card). */
export interface DropAt {
  nodeId: string;
  local: { x: number; y: number };
  flow: { x: number; y: number };
}

const ITEMS: { id: string; icon: IconName; label: string; run(at: DropAt): void }[] = [
  { id: "revise", icon: "replace", label: "Revise the image", run: (at) => addEditNode(at.nodeId, "revise", "", { x: at.flow.x, y: at.flow.y - 60 }) },
  { id: "paint", icon: "brush", label: "Paint an area", run: (at) => addEditNode(at.nodeId, "paint", "", { x: at.flow.x, y: at.flow.y - 60 }) },
  { id: "sketch", icon: "pencil", label: "Draw on it", run: (at) => addEditNode(at.nodeId, "sketch", "", { x: at.flow.x, y: at.flow.y - 60 }) },
  { id: "save", icon: "star", label: "Save to chimeras", run: (at) => {
    const v = (useGraph.getState().nodes.find((n) => n.id === at.nodeId)?.data as VersionData | undefined)?.version;
    if (v) void saveCreature(v, true);
  } },
  { id: "card", icon: "card", label: "Animal card", run: (at) => addCardNode(at.nodeId, { x: at.flow.x, y: at.flow.y - 60 }) },
  { id: "fuse", icon: "fusion", label: "Fuse with another animal", run: (at) => addFusionFrom(at.nodeId, { x: at.flow.x, y: at.flow.y - 60 }) },
];

/** FLORA-style: drag from an image's output onto empty canvas, then choose what to make from it. */
export function DropMenu({ at, onClose }: { at: DropAt; onClose(): void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // Positioned from the drop point (no inline style props: the CSS rules forbid them in JSX).
    el.style.left = `${at.local.x}px`;
    el.style.top = `${at.local.y}px`;
    el.querySelector<HTMLButtonElement>("button")?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    const onDown = (e: PointerEvent) => !el.contains(e.target as Node) && onClose();
    window.addEventListener("keydown", onKey);
    window.addEventListener("pointerdown", onDown);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("pointerdown", onDown);
    };
  }, [at, onClose]);
  return (
    <div ref={ref} className="drop-menu" role="menu" aria-label="Make from this image">
      {ITEMS.map((item) => (
        <button
          key={item.id}
          type="button"
          role="menuitem"
          className="drop-menu__item"
          onClick={() => {
            item.run(at);
            onClose();
          }}
        >
          <Icon name={item.icon} size={16} /> {item.label}
        </button>
      ))}
    </div>
  );
}
