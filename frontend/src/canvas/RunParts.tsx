import { useEffect, useRef, useState } from "react";
import type { AppError } from "../api/errors";
import { presentError } from "../api/errorMessages";
import { copy } from "../copy";
import type { Step } from "../types/api";
import { Icon } from "../ui/Icon";
import { Timeline, type TimelineItem } from "../ui/Timeline";
import { formatSeconds } from "./useNow";

// Shared by every runnable node (Fusion, Field Card, …): step list, error block, retry countdown.

const t = copy.nodes.fusion;

export function stepDuration(s: Step, now: number): string {
  const started = s.startedAt ? Date.parse(s.startedAt) : null;
  const ended = s.endedAt ? Date.parse(s.endedAt) : null;
  return started && s.status !== "skipped" ? formatSeconds((ended ?? now) - started) : "";
}

export function totalMs(steps: Step[]): number {
  const starts = steps.map((s) => (s.startedAt ? Date.parse(s.startedAt) : NaN)).filter(Number.isFinite);
  const ends = steps.map((s) => (s.endedAt ? Date.parse(s.endedAt) : NaN)).filter(Number.isFinite);
  return starts.length && ends.length ? Math.max(...ends) - Math.min(...starts) : 0;
}

export function StepList({ steps, now, allDetails = false }: { steps: Step[]; now: number; allDetails?: boolean }) {
  const done = steps.filter((s) => s.status === "succeeded").length;
  // While running, only the latest finished step explains itself; failures always do.
  const lastDone = [...steps].reverse().find((s) => s.status === "succeeded")?.key;
  const items: TimelineItem[] = steps.map((s) => ({
    key: s.key,
    label: s.label,
    status: s.status,
    statusText: copy.steps[s.status],
    duration: stepDuration(s, now),
    detail: s.detail && (s.status === "failed" || (s.status === "succeeded" && (allDetails || s.key === lastDone))) ? s.detail : undefined,
  }));
  return (
    <div className="steps">
      {allDetails ? null : <p className="steps__count">{t.stepCount(done, steps.length)}</p>}
      <Timeline items={items} dense />
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
