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
import { useWorkspaces } from "../persistence/workspaces";
import { ChimerasPage } from "../screens/ChimerasPage";
import { HomePage } from "../screens/HomePage";
import { LabView } from "../screens/LabView";
import { ConfirmDialog } from "../ui/ConfirmDialog";
import { Banners } from "./Banners";
import { parseRoute, useRoute } from "./route";
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

/** Load the signed-in user's open workspace (and again when they switch); signing out clears it. */
function useWorkspace(): boolean {
  const status = useAuth((s) => s.status);
  const userId = useAuth((s) => s.userId);
  const workspaceId = useWorkspaces((s) => (s.userId === userId ? s.currentId : null));
  const [readyFor, setReadyFor] = useState<string | null>(null);

  useEffect(() => {
    if (status !== "signed-in" || !userId) {
      useGraph.getState().reset();
      useWorkspaces.getState().reset();
      stopFollowingJobs();
      stopAllStreams();
      setReadyFor(null);
      return;
    }
    if (useWorkspaces.getState().userId !== userId) {
      const r = parseRoute(window.location.search);
      void useWorkspaces.getState().init(userId, r.view === "lab" ? r.workspaceId : null);
    }
  }, [status, userId]);

  useEffect(() => {
    if (status !== "signed-in" || !userId || !workspaceId) return;
    let alive = true;
    let stop: (() => void) | null = null;
    setReadyFor(null);
    void restoreWorkspace(userId, workspaceId).then(() => {
      if (!alive) return;
      stop = startAutosave(userId, workspaceId);
      resume();
      setReadyFor(`${userId}:${workspaceId}`);
    });
    return () => {
      alive = false;
      stop?.();
    };
  }, [status, userId, workspaceId]);

  return status === "signed-in" ? readyFor === `${userId}:${workspaceId}` : status !== "loading";
}

export function App() {
  const route = useRoute();
  const ready = useWorkspace();
  const loaded = useWorkspaces((s) => s.loaded);
  // A workspace link (?ws=<id>) opens that workspace.
  const routeWs = route.view === "lab" ? route.workspaceId ?? null : null;
  useEffect(() => {
    if (loaded && routeWs) useWorkspaces.getState().open(routeWs);
  }, [loaded, routeWs]);

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
          {route.view === "chimeras" ? <ChimerasPage /> : route.view === "home" ? <HomePage /> : <LabView ready={ready} runId={route.runId} />}
        </main>
        <Toasts />
        <ShortcutsDialog />
        <ConfirmDialog />
      </div>
    </ReactFlowProvider>
  );
}
