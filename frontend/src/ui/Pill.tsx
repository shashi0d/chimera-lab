import type { ReactNode } from "react";

export type PillTone = "indigo" | "info" | "success" | "warning" | "danger" | "neutral";

/** Tag / status pill: --tint-* ground with the matching *-text colour. */
export function Pill({ tone = "neutral", className, children }: { tone?: PillTone; className?: string; children: ReactNode }) {
  return <span className={`pill pill--${tone}${className ? ` ${className}` : ""}`}>{children}</span>;
}
