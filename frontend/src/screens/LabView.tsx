import { useAuth } from "../auth/auth";
import { Canvas } from "../canvas/Canvas";
import { copy } from "../copy";
import { useGraph } from "../graph/store";
import { ToolsPanel } from "../lab/ToolsPanel";
import { IdentifyDialog } from "../nodes/fusion/IdentifyDialog";
import type { VersionData } from "../nodes/version/types";

/** The selected image card, when exactly one finished image is selected (its tools open beside the canvas). */
function useSelectedVersion(): string | null {
  return useGraph((s) => {
    if (s.selection.length !== 1) return null;
    const n = s.nodes.find((x) => x.id === s.selection[0]);
    return n?.type === "version" && (n.data as VersionData).version ? n.id : null;
  });
}

/** The Lab: the canvas with the selected image's tools (or a run's live trace) docked beside it. */
// The run trace panel (trace/TracePanel) is hidden for now; a run shows on the canvas only.
export function LabView({ ready }: { ready: boolean; runId: string | null }) {
  const status = useAuth((s) => s.status);
  const selected = useSelectedVersion();
  const side = selected ? <ToolsPanel key={selected} nodeId={selected} /> : null;
  return (
    <div className={`workspace${side ? " has-trace" : ""}`} aria-busy={!ready}>
      <h1 className="sr-only">{copy.lab.heading}</h1>
      <div className="workspace__canvas">
        {ready && status === "signed-in" ? (
          <Canvas />
        ) : (
          <div className="workspace__loading" aria-label={copy.lab.loading}>
            <span className="spinner" />
          </div>
        )}
      </div>
      {side}
      <IdentifyDialog />
    </div>
  );
}
