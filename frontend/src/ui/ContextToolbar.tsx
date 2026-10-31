import type { ReactNode } from "react";

/**
 * Glass toolbar above a node. Shown on hover, selection and :focus-within (CSS);
 * hidden with opacity + transform only, so it stays in the tab order and the accessibility tree.
 */
export function ContextToolbar({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="ctx-toolbar nodrag nopan" role="toolbar" aria-label={label}>
      {children}
    </div>
  );
}
