import { copy } from "../../copy";
import { Icon } from "../../ui/Icon";

/** Placeholder for node types this version doesn't know. Never crashes the canvas. */
export function UnsupportedNodeView({ type, catalog }: { type: string; catalog: number }) {
  return (
    <article className="node node--unsupported" aria-label={copy.nodes.unsupportedTitle}>
      <header className="node__header">
        <span className="node__catalog">No.{String(catalog).padStart(2, "0")}</span>
        <Icon name="help" size={16} className="node__glyph" />
        <h3 className="node__title">{copy.nodes.unsupportedTitle}</h3>
      </header>
      <div className="node__body">
        <p className="node__text">{copy.nodes.unsupportedBody(type)}</p>
      </div>
    </article>
  );
}
