import { useConnectivity } from "../connectivity/store";
import { copy } from "../copy";
import { useSaveState } from "../persistence/autosave";
import { IconButton } from "../ui/Button";
import { useUi } from "../ui/uiStore";

export function TopBar() {
  const mode = useConnectivity((s) => s.mode);
  const theme = useUi((s) => s.theme);
  const setTheme = useUi((s) => s.setTheme);
  const setShortcutsOpen = useUi((s) => s.setShortcutsOpen);
  const save = useSaveState((s) => s.state);
  const saveLabel = save === "saving" ? copy.app.saving : save === "saved" ? copy.app.saved : save === "saved-local" ? copy.app.savedLocally : "";

  return (
    <header className="topbar">
      <div className="wordmark">
        <svg className="wordmark__glyph" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
          <path d="M8 22c2-7 6-11 8-11s6 4 8 11" className="wm-arc" />
          <circle cx="11" cy="12" r="2.6" className="wm-a" />
          <path d="M21 9.5l2.6 2.6L21 14.7l-2.6-2.6z" className="wm-b" />
        </svg>
        <h1 className="wordmark__name">{copy.app.name}</h1>
      </div>
      <p className="topbar__doc">
        <span className="topbar__title">{copy.app.untitled}</span>
        {saveLabel ? <span className="topbar__save" aria-live="polite">{saveLabel}</span> : null}
      </p>
      <div className="topbar__actions">
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
