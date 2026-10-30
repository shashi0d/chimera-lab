import { Handle, Position } from "@xyflow/react";
import type { ReactNode } from "react";
import type { PortSpec } from "../graph/types";
import { Icon, type IconName } from "../ui/Icon";

export type Tone = "idle" | "ok" | "running" | "warn" | "error" | "stale";

export interface NodeStatus {
  tone: Tone;
  label: string;
}

const TONE_ICON: Record<Tone, IconName | null> = {
  idle: null,
  ok: "check",
  running: null,
  warn: "alert",
  error: "error",
  stale: "refresh",
};

interface NodeCardProps {
  nodeId: string;
  kind: string;
  catalog: number;
  title: string;
  icon: IconName;
  status?: NodeStatus;
  inputs: PortSpec[];
  outputs: PortSpec[];
  selected: boolean;
  /** Extra state classes (node--running, node--error, …). */
  className?: string;
  /** Hover toolbar actions. */
  toolbar?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}

function portClass(port: PortSpec, kind: "in" | "out", index: number, count: number): string {
  const type = kind === "in" ? port.accepts?.[0] ?? "image" : port.emits ?? "creature";
  return `port port--${kind} port--${type} port--${port.id} port-pos-${index + 1}-of-${count}`;
}

/** Shared specimen-label card: header (catalog no., title, status), body, ports, footer. */
export function NodeCard(props: NodeCardProps) {
  const { nodeId, kind, catalog, title, icon, status, inputs, outputs, selected, className, toolbar, children, footer } = props;
  const statusIcon = status ? TONE_ICON[status.tone] : null;
  return (
    <article
      className={`node node--${kind}${selected ? " is-selected" : ""}${className ? ` ${className}` : ""}`}
      aria-label={`${title}${status ? `, ${status.label}` : ""}`}
      data-node-id={nodeId}
    >
      <header className="node__header">
        <span className="node__catalog">No.{String(catalog).padStart(2, "0")}</span>
        <Icon name={icon} size={16} className="node__glyph" />
        <h3 className="node__title">{title}</h3>
        {status ? (
          <span className={`node__status status--${status.tone}`} role="status">
            {status.tone === "running" ? <span className="pulse-dot" aria-hidden="true" /> : statusIcon ? <Icon name={statusIcon} size={14} /> : <span className="idle-dot" aria-hidden="true" />}
            <span>{status.label}</span>
          </span>
        ) : null}
      </header>
      {toolbar ? <div className="node__toolbar nodrag">{toolbar}</div> : null}
      <div className="node__body">{children}</div>
      {footer ? <footer className="node__footer">{footer}</footer> : null}
      {inputs.map((p, i) => (
        <Handle key={p.id} id={p.id} type="target" position={Position.Left} className={portClass(p, "in", i, inputs.length)} aria-label={`Input ${p.label ?? p.id}`}>
          {p.label ? <span className="port__label">{p.label}</span> : null}
        </Handle>
      ))}
      {outputs.map((p, i) => (
        <Handle key={p.id} id={p.id} type="source" position={Position.Right} className={portClass(p, "out", i, outputs.length)} aria-label={`Output ${p.label ?? p.id}`} />
      ))}
    </article>
  );
}
