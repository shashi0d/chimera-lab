import { useEffect, useRef, useState } from "react";
import type { AppError } from "../api/errors";
import { presentError } from "../api/errorMessages";
import { copy } from "../copy";
import type { Step } from "../types/api";
import { Icon, type IconName } from "../ui/Icon";
import { formatSeconds } from "./useNow";

// Shared by every runnable node (Fusion, Field Card, …): step list, error block, retry countdown.

const t = copy.nodes.fusion;

const STEP_ICON: Record<Step["status"], IconName | null> = {
  pending: null,
  running: null,
  succeeded: "check",
  failed: "error",
  skipped: "minus",
};

export function StepList({ steps, now, allDetails = false }: { steps: Step[]; now: number; allDetails?: boolean }) {
  const done = steps.filter((s) => s.status === "succeeded").length;
  // While running, only the latest finished step explains itself; failures always do.
  const lastDone = [...steps].reverse().find((s) => s.status === "succeeded")?.key;
  return (
    <div className="steps">
      {allDetails ? null : <p className="steps__count">{t.stepCount(done, steps.length)}</p>}
      <ol className="steps__list">
        {steps.map((s) => {
          const started = s.startedAt ? Date.parse(s.startedAt) : null;
          const ended = s.endedAt ? Date.parse(s.endedAt) : null;
          const ms = started ? (ended ?? now) - started : null;
          const icon = STEP_ICON[s.status];
          return (
            <li key={s.key} className={`step step--${s.status}`} aria-current={s.status === "running" ? "step" : undefined}>
              <span className="step__glyph" aria-hidden="true">
                {s.status === "running" ? <span className="pulse-dot" /> : icon ? <Icon name={icon} size={14} /> : <span className="step__hollow" />}
              </span>
              <span className="step__label">
                {s.label}
                <span className="sr-only">: {copy.steps[s.status]}</span>
              </span>
              <span className="step__time">{ms !== null && s.status !== "skipped" ? formatSeconds(ms) : ""}</span>
              {s.detail && (s.status === "failed" || (s.status === "succeeded" && (allDetails || s.key === lastDone))) ? (
                <span className="step__detail">{s.detail}</span>
              ) : null}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

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

/** The footer's primary button is the retry action; this block explains what happened. */
export function ErrorBlock({ err, countdown }: { err: AppError; countdown: number | null }) {
  const p = presentError(err);
  return (
    <div className="node__error" role="alert">
      <p className="node__error-title">
        <Icon name="error" size={14} /> {p.title}
      </p>
      {p.fix ? <p className="node__error-fix">{p.fix}</p> : null}
      {p.errorId ? <p className="node__error-id">{copy.errors.reportId(p.errorId)}</p> : null}
      {countdown !== null ? (
        <p className="node__error-fix" aria-live="polite">
          {t.retryIn(countdown)}
        </p>
      ) : null}
    </div>
  );
}

