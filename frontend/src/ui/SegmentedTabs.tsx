import { useRef, type KeyboardEvent } from "react";

export interface Segment {
  value: string;
  label: string;
  /** Accessible name when the visible label is terse (e.g. "v2" → "Version 2"). */
  ariaLabel?: string;
}

interface Props {
  items: Segment[];
  value: string;
  onChange(value: string): void;
  label: string;
  className?: string;
}

/** ZD SegmentedTabs as a radiogroup: arrow keys move, the active chip is raised. */
export function SegmentedTabs({ items, value, onChange, label, className }: Props) {
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  const idx = Math.max(
    0,
    items.findIndex((i) => i.value === value),
  );
  const onKey = (e: KeyboardEvent) => {
    const step = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = (idx + step + items.length) % items.length;
    const item = items[next];
    if (!item) return;
    onChange(item.value);
    refs.current[next]?.focus();
  };
  return (
    <div className={`segmented nodrag${className ? ` ${className}` : ""}`} role="radiogroup" aria-label={label} onKeyDown={onKey}>
      {items.map((it, i) => {
        const on = i === idx;
        return (
          <button
            key={it.value}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="radio"
            aria-checked={on}
            aria-label={it.ariaLabel}
            tabIndex={on ? 0 : -1}
            className={`segmented__item${on ? " is-active" : ""}`}
            onClick={() => onChange(it.value)}
          >
            {it.label}
          </button>
        );
      })}
    </div>
  );
}
