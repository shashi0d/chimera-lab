import { useReactFlow } from "@xyflow/react";
import { useEffect, useRef } from "react";
import { copy } from "../copy";
import { useGraph } from "../graph/store";
import { getDefinition } from "../nodes/registry";
import { IconButton } from "../ui/Button";
import { useUi } from "../ui/uiStore";

/** Right-hand drawer that hosts a node definition's Panel (e.g. "How this was made"). */
export function SidePanel() {
  const panel = useUi((s) => s.panel);
  const close = useUi((s) => s.closePanel);
  const node = useGraph((s) => (panel ? s.nodes.find((n) => n.id === panel.nodeId) : undefined));
  const closeRef = useRef<HTMLButtonElement>(null);
  const asideRef = useRef<HTMLElement>(null);
  const flow = useReactFlow();
  const opener = useRef<Element | null>(null);

  useEffect(() => {
    if (!panel) return;
    opener.current = document.activeElement;
    closeRef.current?.focus();
    // Keep the described node visible beside the drawer.
    requestAnimationFrame(() => {
      const el = document.querySelector(`.react-flow__node[data-id="${CSS.escape(panel.nodeId)}"]`);
      const drawer = asideRef.current?.getBoundingClientRect();
      if (!el || !drawer) return;
      const r = el.getBoundingClientRect();
      const gap = 32;
      const overlap = r.right + gap - drawer.left;
      if (overlap > 0) {
        const vp = flow.getViewport();
        const canvasLeft = document.querySelector(".canvas")?.getBoundingClientRect().left ?? 0;
        const room = r.left - canvasLeft - 72; // keep clear of the tool rail
        void flow.setViewport({ ...vp, x: vp.x - Math.min(overlap, Math.max(room, 0)) }, { duration: 250 });
      }
    });
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      (opener.current as HTMLElement | null)?.focus?.();
    };
  }, [panel, close, flow]);

  useEffect(() => {
    if (panel && !node) close();
  }, [panel, node, close]);

  const def = node ? getDefinition(node.type) : undefined;
  if (!panel || !node || !def?.Panel) return null;
  const Panel = def.Panel;
  return (
    <aside ref={asideRef} className="side-panel" aria-labelledby="side-panel-title">
      <header className="side-panel__header">
        <h2 id="side-panel-title" className="side-panel__title">
          {copy.panel.title}
        </h2>
        <IconButton ref={closeRef} icon="close" label={copy.panel.close} onClick={close} />
      </header>
      <div className="side-panel__scroll">
        <Panel node={node} onClose={close} />
      </div>
    </aside>
  );
}
