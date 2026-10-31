import type { ReactNode } from "react";

/** Collapsible drawer section (<details>): title, optional count, body. */
export function Section({
  title,
  count,
  open,
  className,
  children,
}: {
  title: string;
  count?: number | string;
  open?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <details className={`section${className ? ` ${className}` : ""}`} open={open}>
      <summary className="section__summary">
        <span className="section__title">{title}</span>
        {count !== undefined ? <span className="section__count">{count}</span> : null}
      </summary>
      <div className="section__body">{children}</div>
    </details>
  );
}
