import { useEffect, useRef } from "react";
import { copy } from "../copy";
import { Button } from "../ui/Button";
import { useUi } from "../ui/uiStore";

export function ShortcutsDialog() {
  const open = useUi((s) => s.shortcutsOpen);
  const setOpen = useUi((s) => s.setShortcutsOpen);
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal?.();
    if (!open && d.open) d.close();
  }, [open]);

  return (
    <dialog ref={ref} className="modal" aria-labelledby="shortcuts-title" onClose={() => setOpen(false)}>
      <h2 id="shortcuts-title" className="modal__title">
        {copy.shortcuts.title}
      </h2>
      <dl className="shortcuts">
        {copy.shortcuts.rows.map(([k, v]) => (
          <div key={k} className="shortcuts__row">
            <dt>
              <kbd>{k}</kbd>
            </dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      <div className="modal__actions">
        <Button variant="primary" onClick={() => setOpen(false)}>
          {copy.shortcuts.close}
        </Button>
      </div>
    </dialog>
  );
}
