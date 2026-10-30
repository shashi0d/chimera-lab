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
  const opener = useRef<Element | null>(null);

  useEffect(() => {
    if (!panel) return;
    opener.current = document.activeElement;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      (opener.current as HTMLElement | null)?.focus?.();
    };
  }, [panel, close]);

  useEffect(() => {
    if (panel && !node) close();
  }, [panel, node, close]);

  const def = node ? getDefinition(node.type) : undefined;
  if (!panel || !node || !def?.Panel) return null;
  const Panel = def.Panel;
  return (
    <aside className="side-panel" aria-labelledby="side-panel-title">
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
