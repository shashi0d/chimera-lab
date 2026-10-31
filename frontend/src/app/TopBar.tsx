import { useConnectivity } from "../connectivity/store";
import { copy } from "../copy";
import { useSaveState } from "../persistence/autosave";
import { useRuns } from "../runs/store";
import { TERMINAL } from "../runs/transport";
import { BrandMark } from "../ui/BrandMark";
import { IconButton } from "../ui/Button";
import { LiveIndicator } from "../ui/LiveIndicator";
import { useUi } from "../ui/uiStore";

export function TopBar() {
  const mode = useConnectivity((s) => s.mode);
  const theme = useUi((s) => s.theme);
  const setTheme = useUi((s) => s.setTheme);
  const setShortcutsOpen = useUi((s) => s.setShortcutsOpen);
  const save = useSaveState((s) => s.state);
  const running = useRuns((s) => Object.values(s.runs).some((r) => !TERMINAL.has(r.status)) || Object.values(s.starting).some(Boolean));
  const saveLabel = save === "saving" ? copy.app.saving : save === "saved" ? copy.app.saved : save === "saved-local" ? copy.app.savedLocally : "";

  return (
    <header className="topbar">
      <BrandMark />
      <p className="topbar__doc">
        <span className="topbar__title">{copy.app.untitled}</span>
        {saveLabel ? (
          <span className="topbar__save" aria-live="polite">
            {saveLabel}
          </span>
        ) : null}
      </p>
      <div className="topbar__actions">
        {running ? <LiveIndicator tone="running" label={copy.status.running} className="topbar__run" /> : null}
        {mode === "mock" ? (
          <span className="mode-badge" data-tooltip={copy.app.modeMockHint} tabIndex={0} aria-label={`${copy.app.modeMock}. ${copy.app.modeMockHint}`}>
            {copy.app.modeMock}
          </span>
        ) : mode === "real" ? (
          <span className="mode-badge mode-badge--live">{copy.app.modeReal}</span>
        ) : null}
        <IconButton
          icon={theme === "dark" ? "sun" : "moon"}
          label={theme === "dark" ? copy.app.themeToLight : copy.app.themeToDark}
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        />
        <IconButton icon="help" label={copy.app.shortcuts} onClick={() => setShortcutsOpen(true)} />
      </div>
    </header>
  );
}
