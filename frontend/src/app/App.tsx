import { ReactFlowProvider } from "@xyflow/react";
import { useEffect, useState } from "react";
import { initAuth, useAuth } from "../auth/auth";
import { startConnectivity } from "../connectivity/store";
import { copy } from "../copy";
import { useLimits } from "../evo/data";
import { stopAllStreams, useEvoRuns } from "../evo/runs";
import { useGraph } from "../graph/store";
import { followJobs, stopFollowingJobs } from "../lab/store";
import { registerRunHandlers } from "../nodes/registry";
import type { FusionData } from "../nodes/fusion/types";
import type { VersionData } from "../nodes/version/types";
import { restoreWorkspace, startAutosave } from "../persistence/autosave";
import { CreationPage } from "../screens/CreationPage";
import { CreaturePage } from "../screens/CreaturePage";
import { GalleryPage } from "../screens/GalleryPage";
import { LabView } from "../screens/LabView";
import { Banners } from "./Banners";
import { useRoute } from "./route";
import { ShortcutsDialog } from "./ShortcutsDialog";
import { Toasts } from "./Toasts";
import { TopBar } from "./TopBar";

/** After a reload: follow every Fusion run again (from the cached trace, then ?after=), and every edit job. */
function resume(): void {
  for (const n of useGraph.getState().nodes) {
    const runId = n.type === "fusion" ? (n.data as FusionData).activeRunId : n.type === "version" && !(n.data as VersionData).version ? (n.data as VersionData).runId : null;
    if (runId) useEvoRuns.getState().attach(runId);
  }
  followJobs();
}

/** Load the signed-in user's Lab (once per user); signing out clears it. */
function useWorkspace(): boolean {
  const status = useAuth((s) => s.status);
  const userId = useAuth((s) => s.userId);
  const [readyFor, setReadyFor] = useState<string | null>(null);

  useEffect(() => {
    if (status !== "signed-in" || !userId) {
      useGraph.getState().reset();
      stopFollowingJobs();
      stopAllStreams();
      setReadyFor(null);
      return;
    }
    let alive = true;
    let stop: (() => void) | null = null;
    void restoreWorkspace(userId).then(() => {
      if (!alive) return;
      stop = startAutosave(userId);
      resume();
      setReadyFor(userId);
    });
    return () => {
      alive = false;
      stop?.();
    };
  }, [status, userId]);

  return status === "signed-in" ? readyFor === userId : status !== "loading";
}

export function App() {
  const route = useRoute();
  const ready = useWorkspace();

  useEffect(() => {
    const stops: Array<() => void> = [];
    stops.push(registerRunHandlers());
    stops.push(startConnectivity());
    void initAuth();
    void useLimits.getState().refresh();
    return () => {
      stops.forEach((s) => s());
      stopAllStreams();
    };
  }, []);

  return (
    <ReactFlowProvider>
      <div className={`app app--${route.view}`}>
        <a className="skip-link" href="#main">
          {copy.app.skip}
        </a>
        <TopBar />
        <Banners />
        <main id="main" className="main" tabIndex={-1}>
          {route.view === "gallery" ? (
            <GalleryPage />
          ) : route.view === "creature" ? (
            <CreaturePage key={route.creatureId} creatureId={route.creatureId} />
          ) : route.view === "creation" ? (
            <CreationPage key={route.publicationId} publicationId={route.publicationId} />
          ) : (
            <LabView ready={ready} runId={route.runId} />
          )}
        </main>
        <Toasts />
        <ShortcutsDialog />
      </div>
    </ReactFlowProvider>
  );
}
