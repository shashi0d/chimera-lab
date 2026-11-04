import { useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";
import { toAppError } from "../api/errors";
import { presentError } from "../api/errorMessages";
import { navigate } from "../app/route";
import { useAuth } from "../auth/auth";
import { copy } from "../copy";
import { evo } from "../evo/index";
import { useTour } from "../tutorial/tourStore";
import { labApi, type LabVersion, type WorkspaceInfo } from "../lab/api";
import { useWorkspaces } from "../persistence/workspaces";
import { Button, IconButton } from "../ui/Button";
import { confirmAction } from "../ui/ConfirmDialog";
import { Icon } from "../ui/Icon";
import { toast } from "../ui/toastStore";

function errorText(e: unknown): string {
  const p = presentError(toAppError(e));
  return `${p.title}${p.fix ? ` ${p.fix}` : ""}`;
}

function edited(iso: string | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const mins = Math.round((Date.now() - d.getTime()) / 60000);
  if (mins < 1) return "Edited just now";
  if (mins < 60) return `Edited ${mins} min ago`;
  if (mins < 60 * 24) return `Edited ${Math.round(mins / 60)} h ago`;
  return `Edited ${d.toLocaleDateString(undefined, { dateStyle: "medium" })}`;
}

export function openWorkspace(id: string): void {
  useWorkspaces.getState().open(id);
  navigate({ view: "lab", runId: null, workspaceId: id });
}

/** A workspace's images (newest first), in a dialog. */
function ImagesDialog({ ws, onClose }: { ws: WorkspaceInfo; onClose(): void }) {
  const [images, setImages] = useState<LabVersion[] | null>(null);
  const titleId = useId();
  useEffect(() => {
    let alive = true;
    labApi
      .workspaceImages(ws.id)
      .then((list) => alive && setImages(list))
      .catch(() => alive && setImages([]));
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => {
      alive = false;
      window.removeEventListener("keydown", onKey);
    };
  }, [ws.id, onClose]);
  return createPortal(
    <div className="dialog-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="dialog library" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <header className="dialog__head">
          <h2 id={titleId}>Images in {ws.name}</h2>
          <IconButton icon="close" label="Close" onClick={onClose} />
        </header>
        {images === null ? <span className="spinner" aria-label="Loading images" /> : null}
        {images && !images.length ? <p className="tools__note">No images in this workspace yet.</p> : null}
        <ul className="library__grid" aria-label={`Images in ${ws.name}`}>
          {images?.map((v) => (
            <li key={v.id} className="library__item library__item--static" title={v.title ?? undefined}>
              <img src={evo().imageUrl(v.imageUrl)} alt={v.title ?? "Generated creature"} loading="lazy" decoding="async" />
              <span className="library__label">{v.title ?? "Untitled"}</span>
            </li>
          ))}
        </ul>
        <div className="confirm-dialog__actions">
          <Button variant="primary" icon="right" onClick={() => openWorkspace(ws.id)}>
            Open workspace
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

function WorkspaceTile({ ws }: { ws: WorkspaceInfo }) {
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(ws.name);
  const [images, setImages] = useState(false);
  const fieldId = useId();
  const thumbs = ws.thumbnails ?? [];

  const rename = async () => {
    setRenaming(false);
    const next = name.trim();
    if (!next || next === ws.name) return setName(ws.name);
    try {
      await useWorkspaces.getState().rename(ws.id, next);
    } catch (e) {
      toast.error(errorText(e));
      setName(ws.name);
    }
  };
  const remove = async () => {
    const n = ws.imageCount ?? 0;
    const ok = await confirmAction({
      title: `Delete "${ws.name}"?`,
      body: `The workspace and ${n === 1 ? "its 1 image" : `all ${n} images in it`} are deleted from the server, with their animal cards. Images another workspace still shows are kept. This can't be undone.`,
      confirmLabel: "Delete workspace",
      danger: true,
    });
    if (!ok) return;
    try {
      const deleted = await useWorkspaces.getState().remove(ws.id);
      toast.success(`Deleted "${ws.name}" and ${deleted === 1 ? "1 image" : `${deleted} images`}.`);
    } catch (e) {
      toast.error(errorText(e));
    }
  };

  return (
    <li className="ws-tile">
      <button type="button" className="ws-tile__open" onClick={() => openWorkspace(ws.id)} aria-label={`Open ${ws.name}`}>
        <span className={`ws-tile__thumbs ws-tile__thumbs--${Math.min(thumbs.length, 4)}`}>
          {thumbs.length ? (
            thumbs.slice(0, 4).map((url) => <img key={url} src={evo().imageUrl(url)} alt="" loading="lazy" decoding="async" />)
          ) : (
            <Icon name="fusion" size={32} />
          )}
        </span>
      </button>
      <div className="ws-tile__info">
        {renaming ? (
          <>
            <label className="sr-only" htmlFor={fieldId}>
              Workspace name
            </label>
            <input
              id={fieldId}
              className="text-input"
              value={name}
              maxLength={80}
              autoFocus
              onChange={(e) => setName(e.target.value)}
              onBlur={() => void rename()}
              onKeyDown={(e) => {
                if (e.key === "Enter") void rename();
                if (e.key === "Escape") {
                  setName(ws.name);
                  setRenaming(false);
                }
              }}
            />
          </>
        ) : (
          <p className="ws-tile__name">{ws.name}</p>
        )}
        <p className="ws-tile__meta">
          {ws.imageCount ?? 0} {ws.imageCount === 1 ? "image" : "images"} · {edited(ws.updatedAt)}
        </p>
        <div className="ws-tile__actions">
          <IconButton icon="image" label={`Images in ${ws.name}`} onClick={() => setImages(true)} />
          <IconButton icon="pencil" label={`Rename ${ws.name}`} onClick={() => setRenaming(true)} />
          <IconButton icon="trash" label={`Delete ${ws.name}`} onClick={() => void remove()} />
        </div>
      </div>
      {images ? <ImagesDialog ws={ws} onClose={() => setImages(false)} /> : null}
    </li>
  );
}

/** The first screen (Figma-style): every workspace as a tile, and a New workspace tile. */
export function HomePage() {
  const status = useAuth((s) => s.status);
  const list = useWorkspaces((s) => s.list);
  const loaded = useWorkspaces((s) => s.loaded);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (status === "signed-in" && loaded) void useWorkspaces.getState().refresh();
  }, [status, loaded]);

  const create = async () => {
    setBusy(true);
    try {
      // The tutorial's last step: open the visitor's empty workspace ("My workspace" is made on the first visit)
      // instead of adding a second, empty one.
      const touring = useTour.getState().active;
      const empty = touring ? list.find((w) => !w.imageCount) : undefined;
      const ws = empty ?? (await useWorkspaces.getState().create(`Untitled workspace ${list.length + 1}`));
      if (touring) useTour.getState().end();
      openWorkspace(ws.id);
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="home" aria-labelledby="home-title">
      <header className="home__head">
        <h1 id="home-title">Workspaces</h1>
        <Button variant="primary" icon="plus" busy={busy} disabled={busy} onClick={() => void create()} data-tour="new-workspace">
          New workspace
        </Button>
      </header>
      {!loaded ? <span className="spinner" aria-label="Loading workspaces" /> : null}
      <ul className="home__grid">
        <li className="ws-tile ws-tile--new">
          <button type="button" className="ws-tile__open" onClick={() => void create()} disabled={busy} data-tour="new-workspace">
            <span className="ws-tile__thumbs">
              <Icon name="plus" size={32} />
            </span>
          </button>
          <div className="ws-tile__info">
            <p className="ws-tile__name">New workspace</p>
            <p className="ws-tile__meta">An empty canvas</p>
          </div>
        </li>
        <li className="ws-tile ws-tile--tutorial">
          <button type="button" className="ws-tile__open" onClick={() => void useTour.getState().start()} aria-label={copy.tour.take}>
            <span className="ws-tile__thumbs">
              <Icon name="help" size={32} />
            </span>
          </button>
          <div className="ws-tile__info">
            <p className="ws-tile__name">{copy.tour.take}</p>
            <p className="ws-tile__meta">{copy.tour.takeMeta}</p>
          </div>
        </li>
        {list.map((ws) => (
          <WorkspaceTile key={ws.id} ws={ws} />
        ))}
      </ul>
    </section>
  );
}
