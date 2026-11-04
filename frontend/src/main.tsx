import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles/theme.css";
import { App } from "./app/App";
import { AppErrorBoundary } from "./app/AppErrorBoundary";
import { useUi } from "./ui/uiStore";

document.documentElement.setAttribute("data-theme", useUi.getState().theme);

const el = document.getElementById("root");
if (el) {
  createRoot(el).render(
    <StrictMode>
      <AppErrorBoundary>
        <App />
      </AppErrorBoundary>
    </StrictMode>,
  );
}
