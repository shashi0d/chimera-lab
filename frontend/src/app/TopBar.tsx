import { signOut, useAuth } from "../auth/auth";
import { copy } from "../copy";
import { derived, isTerminal, useEvoRuns } from "../evo/runs";
import { useSaveState } from "../persistence/autosave";
import { BrandMark } from "../ui/BrandMark";
import { IconButton } from "../ui/Button";
import { LiveIndicator } from "../ui/LiveIndicator";
import { useUi } from "../ui/uiStore";
import { hrefFor, linkHandler, useRoute, type Route } from "./route";

function NavLink({ to, label, current }: { to: Route; label: string; current: boolean }) {
  return (
    <a className={`topnav__link${current ? " is-current" : ""}`} href={hrefFor(to)} onClick={linkHandler(to)} aria-current={current ? "page" : undefined}>
      {label}
    </a>
  );
}

export function TopBar() {
  const auth = useAuth((s) => s.status);
  const email = useAuth((s) => s.email);
  const theme = useUi((s) => s.theme);
  const setTheme = useUi((s) => s.setTheme);
  const setShortcutsOpen = useUi((s) => s.setShortcutsOpen);
  const save = useSaveState((s) => s.state);
  const route = useRoute();
  const liveRunId = useEvoRuns((s) => Object.values(s.runs).find((r) => !isTerminal(derived(r)!.status) && derived(r)!.status !== "loading")?.runId ?? null);
  const saveLabel = save === "saving" ? copy.app.saving : save === "saved" ? "Saved" : save === "saved-local" ? copy.app.savedLocally : "";
  const inLab = route.view === "lab";

  return (
    <header className="topbar">
      <a className="topbar__brand" href={hrefFor({ view: "gallery" })} onClick={linkHandler({ view: "gallery" })} aria-label={copy.nav.home}>
        <BrandMark />
      </a>
      <nav className="topnav" aria-label={copy.nav.label}>
        <NavLink to={{ view: "gallery" }} label={copy.nav.gallery} current={route.view === "gallery" || route.view === "creature" || route.view === "creation"} />
        <NavLink to={{ view: "lab", runId: null }} label={copy.nav.lab} current={inLab} />
      </nav>
      <p className="topbar__doc">
        {inLab ? (
          <>
            <span className="topbar__title">{copy.app.untitled}</span>
            {saveLabel ? (
              <span className="topbar__save" aria-live="polite">
                {saveLabel}
              </span>
            ) : null}
          </>
        ) : null}
      </p>
      <div className="topbar__actions">
        {liveRunId && !(inLab && route.runId === liveRunId) ? (
          <a className="topbar__run" href={hrefFor({ view: "lab", runId: liveRunId })} onClick={linkHandler({ view: "lab", runId: liveRunId })} aria-label={copy.app.openRun}>
            <LiveIndicator tone="running" label={copy.status.running} />
          </a>
        ) : null}
        {auth === "signed-in" ? (
          <span className="topbar__account">
            <span className="topbar__email" title={email ?? undefined}>
              {email}
            </span>
            <button type="button" className="btn btn--ghost btn--sm" onClick={() => void signOut()}>
              Sign out
            </button>
          </span>
        ) : auth === "signed-out" && !inLab ? (
          <a className="btn btn--secondary btn--sm" href={hrefFor({ view: "lab", runId: null })} onClick={linkHandler({ view: "lab", runId: null })}>
            Sign in
          </a>
        ) : null}
        <IconButton
          icon={theme === "dark" ? "sun" : "moon"}
          label={theme === "dark" ? copy.app.themeToLight : copy.app.themeToDark}
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        />
        {inLab ? <IconButton icon="help" label={copy.app.shortcuts} onClick={() => setShortcutsOpen(true)} /> : null}
      </div>
    </header>
  );
}
