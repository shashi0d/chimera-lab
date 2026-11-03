import { ReactFlowProvider } from "@xyflow/react";
import { useEffect, useState } from "react";
import { startConnectivity } from "../connectivity/store";
import { copy } from "../copy";
import { useLimits } from "../evo/data";
import { stopAllStreams, useEvoRuns } from "../evo/runs";
import { useGraph } from "../graph/store";
import { registerRunHandlers } from "../nodes/registry";
import type { FusionData } from "../nodes/fusion/types";
import { restoreGraph, startAutosave } from "../persistence/autosave";
import { CreaturePage } from "../screens/CreaturePage";
import { GalleryPage } from "../screens/GalleryPage";
import { LabView } from "../screens/LabView";
import { Studio } from "../screens/Studio";
import { Banners } from "./Banners";
import { useRoute } from "./route";
import { ShortcutsDialog } from "./ShortcutsDialog";
import { Toasts } from "./Toasts";
import { TopBar } from "./TopBar";

/** Test hook: render-time crash of the whole app shell. */
function AppCrash(): never {
  throw new Error("Forced app crash (test hook)");
}

/** After a reload: follow every Fusion node's latest run again (from the cached trace, then ?after=). */
function resumeRuns(): void {
  for (const n of useGraph.getState().nodes) {
    const runId = (n.data as FusionData).activeRunId;
    if (n.type === "fusion" && runId) useEvoRuns.getState().attach(runId);
  }
}

export function App({ crash = false }: { crash?: boolean }) {
  const [ready, setReady] = useState(false);
  const route = useRoute();

  useEffect(() => {
    const stops: Array<() => void> = [];
    let alive = true;
    stops.push(registerRunHandlers());
    stops.push(startConnectivity());
    void useLimits.getState().refresh();
    void restoreGraph().then(() => {
      if (!alive) return;
      stops.push(startAutosave());
      resumeRuns();
      setReady(true);
    });
    return () => {
      alive = false;
      stops.forEach((s) => s());
      stopAllStreams();
    };
  }, []);

  if (crash) return <AppCrash />;

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
          ) : route.view === "studio" ? (
            <Studio />
          ) : route.view === "creature" ? (
            <CreaturePage key={route.creatureId} creatureId={route.creatureId} />
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
