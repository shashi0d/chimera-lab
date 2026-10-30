import { Component, type ErrorInfo, type ReactNode } from "react";
import { shortId } from "../api/errors";
import { copy } from "../copy";
import { Button } from "../ui/Button";

interface State {
  error: Error | null;
  id: string;
}

/** Last line of defence: the canvas is autosaved, so a reload recovers everything. */
export class AppErrorBoundary extends Component<{ children: ReactNode }, State> {
  override state: State = { error: null, id: "" };

  static getDerivedStateFromError(error: Error): State {
    return { error, id: shortId() };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(`[app] crashed (${this.state.id})`, error, info.componentStack);
  }

  override render() {
    if (!this.state.error) return this.props.children;
    return (
      <main className="app-crash" role="alert">
        <div className="app-crash__card">
          <h1 className="app-crash__title">{copy.app_crash.title}</h1>
          <p className="app-crash__body">{copy.app_crash.body}</p>
          <Button variant="primary" icon="refresh" onClick={() => window.location.reload()}>
            {copy.app_crash.reload}
          </Button>
          <p className="app-crash__id">{copy.app_crash.errorId(this.state.id)}</p>
        </div>
      </main>
    );
  }
}
