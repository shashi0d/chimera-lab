import { StrictMode, useSyncExternalStore } from "react";
import { createRoot } from "react-dom/client";
import "./styles/theme.css";
import { App } from "./app/App";
import { AppErrorBoundary } from "./app/AppErrorBoundary";
import { appCrashSignal } from "./test-hooks/signal";
import { useUi } from "./ui/uiStore";

document.documentElement.setAttribute("data-theme", useUi.getState().theme);

if (import.meta.env.MODE === "test") {
  void import("./test-hooks/install").then((m) => m.install());
}

function Root() {
  const crash = useSyncExternalStore(appCrashSignal.subscribe, appCrashSignal.get);
  return (
    <AppErrorBoundary>
      <App crash={crash} />
    </AppErrorBoundary>
  );
}

const el = document.getElementById("root");
if (el) {
  createRoot(el).render(
    <StrictMode>
      <Root />
    </StrictMode>,
  );
}
