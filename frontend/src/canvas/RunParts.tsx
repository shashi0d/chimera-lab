import { useEffect, useRef, useState } from "react";
import type { AppError } from "../api/errors";
import { presentError } from "../api/errorMessages";
import { copy } from "../copy";
import { Icon } from "../ui/Icon";

// Shared by the Fusion node and the trace panel: the error block and the retry countdown.

/** Auto-retry countdown for RATE_LIMITED (uses retryAfterMs). */
export function useCountdown(err: AppError | null | undefined, onDone: () => void): number | null {
  const [left, setLeft] = useState<number | null>(null);
  const fired = useRef<AppError | null>(null);
  const done = useRef(onDone);
  done.current = onDone;
  useEffect(() => {
    if (!err || err.code !== "RATE_LIMITED" || fired.current === err) {
      setLeft(null);
      return;
    }
    const until = Date.now() + Math.max(1000, err.retryAfterMs ?? 4000);
    const tick = () => {
      const ms = until - Date.now();
      if (ms <= 0) {
        fired.current = err;
        setLeft(null);
        done.current();
      } else setLeft(Math.ceil(ms / 1000));
    };
    tick();
    const id = setInterval(tick, 250);
    return () => clearInterval(id);
  }, [err]);
  return left;
}

/** Title, what to change, and an error id when there is one. The retry action sits next to it. */
export function ErrorBlock({ err, countdown = null, className }: { err: AppError; countdown?: number | null; className?: string }) {
  const p = presentError(err);
  return (
    <div className={`node__error${className ? ` ${className}` : ""}`} role="alert">
      <p className="node__error-title">
        <Icon name="error" size={14} /> {p.title}
      </p>
      {p.fix ? <p className="node__error-fix">{p.fix}</p> : null}
      {p.errorId ? <p className="node__error-id">{copy.errors.reportId(p.errorId)}</p> : null}
      {countdown !== null ? (
        <p className="node__error-fix" aria-live="polite">
          {copy.nodes.fusion.retryIn(countdown)}
        </p>
      ) : null}
    </div>
  );
}
