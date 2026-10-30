import { useEffect } from "react";
import { IconButton } from "../ui/Button";
import { Icon, type IconName } from "../ui/Icon";
import { useToasts, type Toast } from "../ui/toastStore";

const ICON: Record<Toast["kind"], IconName> = { info: "info", success: "check", warning: "alert", error: "error" };

function ToastItem({ t }: { t: Toast }) {
  const dismiss = useToasts((s) => s.dismiss);
  useEffect(() => {
    const id = setTimeout(() => dismiss(t.id), t.timeoutMs);
    return () => clearTimeout(id);
  }, [t.id, t.timeoutMs, dismiss]);
  return (
    <li className={`toast toast--${t.kind}`} role={t.kind === "error" ? "alert" : "status"}>
      <Icon name={ICON[t.kind]} size={16} />
      <p className="toast__msg">{t.message}</p>
      {t.action ? (
        <button type="button" className="toast__action" onClick={t.action.run}>
          {t.action.label}
        </button>
      ) : null}
      <IconButton icon="close" label="Dismiss" className="toast__close" onClick={() => dismiss(t.id)} />
    </li>
  );
}

export function Toasts() {
  const toasts = useToasts((s) => s.toasts);
  return (
    <ol className="toast-stack" aria-live="polite" aria-label="Notifications">
      {toasts.map((t) => (
        <ToastItem key={t.id} t={t} />
      ))}
    </ol>
  );
}
