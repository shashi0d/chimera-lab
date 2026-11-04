import { useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";
import { evo } from "../evo/index";
import { IconButton } from "../ui/Button";
import { CodexCard } from "./CodexCard";
import type { LabVersion } from "./api";

/** The full animal card in a modal: it opens with its animation; closing the card closes the modal. */
export function CardModal({ version, onChange, onClose, editable = true }: {
  version: LabVersion;
  onChange?: (v: LabVersion) => void;
  onClose(): void;
  editable?: boolean;
}) {
  const titleId = useId();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  const name = version.card?.profile?.name ?? version.profile?.name ?? version.title ?? "Creature";
  return createPortal(
    <div className="dialog-backdrop card-modal__backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="card-modal" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <h2 id={titleId} className="sr-only">
          {name}, animal card
        </h2>
        <IconButton icon="close" label="Close the card" className="card-modal__close" onClick={onClose} />
        <CodexCard version={version} onChange={onChange} autoOpen editable={editable} onClose={onClose} />
      </div>
    </div>,
    document.body,
  );
}

/**
 * The small animal card (the closed card: creature and name). A click opens the full card in a modal. Used on the
 * Chimeras page and on the canvas.
 */
export function CardTile({ version, onChange, editable = true }: { version: LabVersion; onChange?: (v: LabVersion) => void; editable?: boolean }) {
  const [open, setOpen] = useState(false);
  const p = version.card?.profile ?? version.profile;
  const name = p?.name ?? version.title ?? "Unnamed creature";
  const drawing = version.card?.status === "running";
  const accent = useAccent(p?.accent_color);
  return (
    <>
      <button type="button" className="card-tile nodrag" ref={accent} onClick={() => setOpen(true)} aria-label={`${name}. Open card`}>
        <span className="card-tile__slate" aria-hidden="true" />
        <img className="card-tile__img" src={evo().imageUrl(version.imageUrl)} alt="" loading="lazy" decoding="async" />
        <span className="card-tile__name">{name}</span>
        {p?.trait ? <span className="card-tile__trait">{p.trait}</span> : null}
        {drawing ? <span className="card-tile__status">Drawing the card…</span> : null}
      </button>
      {open ? <CardModal version={version} onChange={onChange} onClose={() => setOpen(false)} editable={editable} /> : null}
    </>
  );
}

function useAccent(colour: string | undefined) {
  const [el, setEl] = useState<HTMLButtonElement | null>(null);
  useEffect(() => {
    if (el && colour) el.style.setProperty("--slate", colour);
  }, [el, colour]);
  return setEl;
}
