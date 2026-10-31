import { Component, type ErrorInfo, type ReactNode } from "react";
import { copy } from "../copy";
import { Button } from "../ui/Button";
import { Icon } from "../ui/Icon";

interface Props {
  nodeId: string;
  children: ReactNode;
}

interface State {
  error: Error | null;
  attempt: number;
}

/** One node crashing renders a card in its place; the canvas stays usable (TASKSHEET 7.6). */
export class NodeErrorBoundary extends Component<Props, State> {
  override state: State = { error: null, attempt: 0 };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(`[node ${this.props.nodeId}] render failed`, error, info.componentStack);
  }

  override render() {
    if (!this.state.error) return <div key={this.state.attempt}>{this.props.children}</div>;
    return (
      <article className="node node--crashed" role="alert" data-node-id={this.props.nodeId}>
        <header className="node__header">
          <div className="node__head-row">
            <p className="node__kicker">{copy.nodes.crashKicker}</p>
            <span className="live status--error">
              <Icon name="error" size={14} />
              <span className="live__label">{copy.status.error}</span>
            </span>
          </div>
          <h3 className="node__title">{copy.nodes.crashTitle}</h3>
        </header>
        <div className="node__body">
          <p className="node__text">{copy.nodes.crashBody}</p>
          <Button size="sm" icon="refresh" className="nodrag" onClick={() => this.setState((s) => ({ error: null, attempt: s.attempt + 1 }))}>
            {copy.nodes.crashReload}
          </Button>
        </div>
      </article>
    );
  }
}
