import type { ReactNode } from "react";

/** ZD dashboard stat: mono kicker, display value, mono meta line. A missing value reads "unknown", never 0. */
export function StatCard({
  kicker,
  value,
  meta,
  tone,
}: {
  kicker: string;
  value: ReactNode | null | undefined;
  meta?: ReactNode;
  tone?: "success" | "warning" | "danger" | "info";
}) {
  const missing = value === null || value === undefined || value === "";
  return (
    <div className="stat">
      <p className="stat__kicker">{kicker}</p>
      <p className={`stat__value${missing ? " stat__value--unknown" : ""}`}>{missing ? "unknown" : value}</p>
      {meta ? <p className={`stat__meta${tone ? ` stat__meta--${tone}` : ""}`}>{meta}</p> : null}
    </div>
  );
}
