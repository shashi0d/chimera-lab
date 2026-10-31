import { Handle, Position } from "@xyflow/react";
import type { ReactNode } from "react";
import type { PortSpec } from "../graph/types";
import { ContextToolbar } from "../ui/ContextToolbar";
import { LiveIndicator, type Tone } from "../ui/LiveIndicator";

export type { Tone };

export interface NodeStatus {
  tone: Tone;
  label: string;
}

interface NodeCardProps {
  nodeId: string;
  kind: string;
  /** Mono label above the title ("INPUT A", "FUSION", "RESULT · V2"). */
  kicker: string;
  title: string;
  status?: NodeStatus;
  inputs: PortSpec[];
  outputs: PortSpec[];
  selected: boolean;
  /** Extra state classes (node--running, node--error, …). */
  className?: string;
  /** Image that fills the top of the card, edge to edge. */
  media?: ReactNode;
  /** Contextual toolbar actions (shown on hover, selection and focus). */
  toolbar?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
}

function portClass(port: PortSpec, kind: "in" | "out", index: number, count: number): string {
  const type = kind === "in" ? (port.accepts?.[0] ?? "image") : (port.emits ?? "creature");
  return `port port--${kind} port--${type} port--${port.id} port-pos-${index + 1}-of-${count}`;
}

/** ZD Card for every node: optional media, kicker + title + LiveIndicator, body, footer, ports. */
export function NodeCard(props: NodeCardProps) {
  const { nodeId, kind, kicker, title, status, inputs, outputs, selected, className, media, toolbar, children, footer } = props;
  return (
    <article
      className={`node node--${kind}${media ? " node--has-media" : ""}${selected ? " is-selected" : ""}${className ? ` ${className}` : ""}`}
      aria-label={`${title}${status ? `, ${status.label}` : ""}`}
      data-node-id={nodeId}
    >
      {toolbar ? <ContextToolbar label={`${title} actions`}>{toolbar}</ContextToolbar> : null}
      {media ? <div className="node__media">{media}</div> : null}
      <header className="node__header">
        <div className="node__head-row">
          <p className="node__kicker">{kicker}</p>
          {status ? <LiveIndicator tone={status.tone} label={status.label} className="node__status" /> : null}
        </div>
        <h3 className="node__title">{title}</h3>
      </header>
      {children ? <div className="node__body">{children}</div> : null}
      {footer ? <footer className="node__footer">{footer}</footer> : null}
      {inputs.map((p, i) => (
        <Handle key={p.id} id={p.id} type="target" position={Position.Left} className={portClass(p, "in", i, inputs.length)}>
          {p.label ? <span className="port__label">{p.label}</span> : null}
        </Handle>
      ))}
      {outputs.map((p, i) => (
        <Handle key={p.id} id={p.id} type="source" position={Position.Right} className={portClass(p, "out", i, outputs.length)} />
      ))}
    </article>
  );
}
