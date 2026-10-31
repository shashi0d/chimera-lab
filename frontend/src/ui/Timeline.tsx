import type { ReactNode } from "react";
import { Icon, type IconName } from "./Icon";

export type TimelineStatus = "pending" | "running" | "succeeded" | "failed" | "skipped";

export interface TimelineItem {
  key: string;
  label: string;
  status: TimelineStatus;
  /** Word for the status, read by screen readers ("Done", "In progress"). */
  statusText: string;
  duration?: string;
  detail?: ReactNode;
}

const ICON: Record<TimelineStatus, IconName | null> = {
  pending: null,
  running: null,
  succeeded: "check",
  failed: "error",
  skipped: "minus",
};

/** ZD Timeline: a vertical event list with a rail; `dense` tightens it for nodes. */
export function Timeline({ items, dense = false, label }: { items: TimelineItem[]; dense?: boolean; label?: string }) {
  return (
    <ol className={`timeline steps__list${dense ? " timeline--dense" : ""}`} aria-label={label}>
      {items.map((s) => {
        const icon = ICON[s.status];
        return (
          <li key={s.key} className={`timeline__item step step--${s.status}`} aria-current={s.status === "running" ? "step" : undefined}>
            <span className="timeline__marker step__glyph" aria-hidden="true">
              {s.status === "running" ? <span className="live__dot" /> : icon ? <Icon name={icon} size={12} /> : <span className="step__hollow" />}
            </span>
            <span className="timeline__label step__label">
              {s.label}
              <span className="sr-only">: {s.statusText}</span>
            </span>
            <span className="timeline__time step__time">{s.duration ?? ""}</span>
            {s.detail ? <span className="timeline__detail step__detail">{s.detail}</span> : null}
          </li>
        );
      })}
    </ol>
  );
}
