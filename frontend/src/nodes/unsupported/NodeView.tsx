import { copy } from "../../copy";

/** Placeholder for node types this version doesn't know. Never crashes the canvas. */
export function UnsupportedNodeView({ type }: { type: string; catalog?: number }) {
  return (
    <article className="node node--unsupported" aria-label={copy.nodes.unsupportedTitle}>
      <header className="node__header">
        <div className="node__head-row">
          <p className="node__kicker">{type}</p>
        </div>
        <h3 className="node__title">{copy.nodes.unsupportedTitle}</h3>
      </header>
      <div className="node__body">
        <p className="node__text">{copy.nodes.unsupportedBody(type)}</p>
      </div>
    </article>
  );
}
