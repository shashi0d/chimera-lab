import { ReactFlowProvider } from "@xyflow/react";
import { useEffect, useState } from "react";
import { Canvas } from "../canvas/Canvas";
import { startConnectivity } from "../connectivity/store";
import { startUploadQueue } from "../nodes/image-input/uploads";
import { registerFusionRunHandler } from "../nodes/fusion/actions";
import { restoreGraph, startAutosave } from "../persistence/autosave";
import { resumeAllRuns, stopAllRuns } from "../runs/store";
import { useUi } from "../ui/uiStore";
import { Banners } from "./Banners";
import { ShortcutsDialog } from "./ShortcutsDialog";
import { SidePanel } from "./SidePanel";
import { Toasts } from "./Toasts";
import { TopBar } from "./TopBar";

/** Test hook: render-time crash of the whole app shell. */
function AppCrash(): never {
  throw new Error("Forced app crash (test hook)");
}

export function App({ crash = false }: { crash?: boolean }) {
  const [ready, setReady] = useState(false);
  const panelOpen = useUi((s) => Boolean(s.panel));

  useEffect(() => {
    const stops: Array<() => void> = [];
    let alive = true;
    stops.push(registerFusionRunHandler());
    stops.push(startConnectivity());
    void restoreGraph().then(() => {
      if (!alive) return;
      stops.push(startAutosave());
      stops.push(startUploadQueue());
      resumeAllRuns();
      setReady(true);
    });
    return () => {
      alive = false;
      stops.forEach((s) => s());
      stopAllRuns();
    };
  }, []);

  if (crash) return <AppCrash />;

  return (
    <ReactFlowProvider>
      <div className={`app${panelOpen ? " has-panel" : ""}`}>
        <a className="skip-link" href="#canvas-region">
          Skip to canvas
        </a>
        <TopBar />
        <Banners />
        <main id="canvas-region" className="workspace" aria-busy={!ready}>
          {ready ? <Canvas /> : <div className="workspace__loading" aria-label="Loading canvas"><span className="spinner" /></div>}
          <SidePanel />
        </main>
        <Toasts />
        <ShortcutsDialog />
      </div>
    </ReactFlowProvider>
  );
}
