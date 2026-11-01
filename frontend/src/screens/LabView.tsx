import { Canvas } from "../canvas/Canvas";
import { copy } from "../copy";
import { IdentifyDialog } from "../nodes/fusion/IdentifyDialog";
import { TracePanel } from "../trace/TracePanel";

/** The canvas (make a new creature) with the live trace of the run in the URL docked beside it. */
export function LabView({ ready, runId }: { ready: boolean; runId: string | null }) {
  return (
    <div className={`workspace${runId ? " has-trace" : ""}`} aria-busy={!ready}>
      <h1 className="sr-only">{copy.lab.heading}</h1>
      <div className="workspace__canvas">
        {ready ? (
          <Canvas />
        ) : (
          <div className="workspace__loading" aria-label={copy.lab.loading}>
            <span className="spinner" />
          </div>
        )}
      </div>
      {runId ? <TracePanel key={runId} runId={runId} /> : null}
      <IdentifyDialog />
    </div>
  );
}
