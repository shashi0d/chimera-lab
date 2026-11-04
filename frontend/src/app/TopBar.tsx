import { useState } from "react";
import { useAuth } from "../auth/auth";
import { copy } from "../copy";
import { derived, isTerminal, useEvoRuns } from "../evo/runs";
import { saveNow, useSaveState } from "../persistence/autosave";
import { useWorkspaces } from "../persistence/workspaces";
import { BrandMark } from "../ui/BrandMark";
import { Button, IconButton } from "../ui/Button";
import { LiveIndicator } from "../ui/LiveIndicator";
import { toast } from "../ui/toastStore";
import { useUi } from "../ui/uiStore";
import { hrefFor, linkHandler, useRoute, type Route } from "./route";

function NavLink({ to, label, current }: { to: Route; label: string; current: boolean }) {
  return (
    <a className={`topnav__link${current ? " is-current" : ""}`} href={hrefFor(to)} onClick={linkHandler(to)} aria-current={current ? "page" : undefined}>
      {label}
    </a>
  );
}

/** The open workspace's name: click to rename it in place. */
function WorkspaceName() {
  const ws = useWorkspaces((s) => s.list.find((w) => w.id === s.currentId));
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  if (!ws) return <span className="topbar__title">{copy.app.untitled}</span>;
  const commit = async () => {
    setEditing(false);
    const next = name.trim();
    if (!next || next === ws.name) return;
    try {
      await useWorkspaces.getState().rename(ws.id, next);
    } catch {
      toast.error("The workspace could not be renamed.");
    }
  };
  return editing ? (
    <input
      className="text-input topbar__title-input"
      aria-label="Workspace name"
      value={name}
      maxLength={80}
      autoFocus
      onChange={(e) => setName(e.target.value)}
      onBlur={() => void commit()}
      onKeyDown={(e) => {
        if (e.key === "Enter") void commit();
        if (e.key === "Escape") setEditing(false);
      }}
    />
  ) : (
    <button
      type="button"
      className="topbar__title topbar__title--button"
      title="Rename this workspace"
      onClick={() => {
        setName(ws.name);
        setEditing(true);
      }}
    >
      {ws.name}
    </button>
  );
}

export function TopBar() {
  const auth = useAuth((s) => s.status);
  const theme = useUi((s) => s.theme);
  const setTheme = useUi((s) => s.setTheme);
  const setShortcutsOpen = useUi((s) => s.setShortcutsOpen);
  const save = useSaveState((s) => s.state);
  const route = useRoute();
  const [saving, setSaving] = useState(false);
  const liveRunId = useEvoRuns((s) => Object.values(s.runs).find((r) => !isTerminal(derived(r)!.status) && derived(r)!.status !== "loading")?.runId ?? null);
  const saveLabel = save === "saving" ? copy.app.saving : save === "saved" ? "Saved" : save === "saved-local" ? copy.app.savedLocally : "";
  const inLab = route.view === "lab";
  const currentWs = useWorkspaces((s) => s.currentId);
  const signedIn = auth === "signed-in";

  const saveClick = async () => {
    setSaving(true);
    try {
      await saveNow();
    } finally {
      setSaving(false);
    }
  };

  return (
    <header className="topbar">
      <a className="topbar__brand" href={hrefFor({ view: "home" })} onClick={linkHandler({ view: "home" })} aria-label={copy.nav.home}>
        <BrandMark />
      </a>
      <nav className="topnav" aria-label={copy.nav.label}>
        <NavLink to={{ view: "home" }} label={copy.nav.workspaces} current={route.view === "home"} />
        <NavLink to={{ view: "chimeras" }} label={copy.nav.chimeras} current={route.view === "chimeras"} />
      </nav>
      <div className="topbar__doc">
        {inLab && signedIn ? (
          <>
            <WorkspaceName />
            <Button size="sm" variant="ghost" icon="check" busy={saving} disabled={saving} onClick={() => void saveClick()}>
              Save
            </Button>
            {saveLabel ? (
              <span className="topbar__save" aria-live="polite">
                {saveLabel}
              </span>
            ) : null}
          </>
        ) : null}
      </div>
      <div className="topbar__actions">
        {liveRunId && !(inLab && route.runId === liveRunId) ? (
          <a className="topbar__run" href={hrefFor({ view: "lab", runId: liveRunId, workspaceId: currentWs })} onClick={linkHandler({ view: "lab", runId: liveRunId, workspaceId: currentWs })} aria-label={copy.app.openRun}>
            <LiveIndicator tone="running" label={copy.status.running} />
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
