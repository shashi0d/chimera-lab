import { useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";
import { create } from "zustand";
import { Button } from "./Button";

/** One confirmation at a time: `confirmAction(...)` opens the dialog and resolves true (confirm) or false. */
interface Ask {
  title: string;
  body: string;
  confirmLabel: string;
  danger?: boolean;
  resolve(ok: boolean): void;
}

const useConfirm = create<{ ask: Ask | null }>()(() => ({ ask: null }));

export function confirmAction(opts: Omit<Ask, "resolve">): Promise<boolean> {
  useConfirm.getState().ask?.resolve(false);
  return new Promise((resolve) => useConfirm.setState({ ask: { ...opts, resolve } }));
}

function answer(ok: boolean): void {
  const ask = useConfirm.getState().ask;
  useConfirm.setState({ ask: null });
  ask?.resolve(ok);
}

export function ConfirmDialog() {
  const ask = useConfirm((s) => s.ask);
  const titleId = useId();
  const bodyId = useId();
  const cancelRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!ask) return;
    cancelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        answer(false);
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [ask]);
  if (!ask) return null;
  return createPortal(
    <div className="dialog-backdrop" onMouseDown={(e) => e.target === e.currentTarget && answer(false)}>
      <div className="dialog confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={bodyId}>
        <h2 id={titleId} className="confirm-dialog__title">
          {ask.title}
        </h2>
        <p id={bodyId} className="confirm-dialog__body">
          {ask.body}
        </p>
        <div className="confirm-dialog__actions">
          <Button ref={cancelRef} variant="ghost" onClick={() => answer(false)}>
            Cancel
          </Button>
          <Button variant={ask.danger ? "danger" : "primary"} icon={ask.danger ? "trash" : "check"} onClick={() => answer(true)}>
            {ask.confirmLabel}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
