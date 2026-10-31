import { Icon, type IconName } from "./Icon";

export type Tone = "idle" | "ok" | "running" | "warn" | "error" | "stale";

const TONE_ICON: Record<Tone, IconName | null> = {
  idle: null,
  ok: "check",
  running: null,
  warn: "alert",
  error: "error",
  stale: "refresh",
};

/** ZD LiveIndicator: a tinted pill with a word; running pulses. Colour is never the only signal. */
export function LiveIndicator({ tone, label, className }: { tone: Tone; label: string; className?: string }) {
  const icon = TONE_ICON[tone];
  return (
    <span className={`live status--${tone}${className ? ` ${className}` : ""}`} role="status">
      {tone === "running" ? (
        <span className="live__dot" aria-hidden="true" />
      ) : icon ? (
        <Icon name={icon} size={14} />
      ) : (
        <span className="live__dot live__dot--still" aria-hidden="true" />
      )}
      <span className="live__label">{label}</span>
    </span>
  );
}
