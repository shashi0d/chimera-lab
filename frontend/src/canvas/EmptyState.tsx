import { copy } from "../copy";
import { Button } from "../ui/Button";
import { pickImages } from "./filePicker";

/** Centered invitation on an empty canvas; the whole canvas is the drop zone. */
export function EmptyState({ onAddFiles }: { onAddFiles: (files: File[]) => void }) {
  return (
    <section className="empty-state" aria-labelledby="empty-title">
      <div className="empty-state__card">
        <svg className="empty-state__art" viewBox="0 0 160 72" aria-hidden="true" focusable="false">
          <rect x="4" y="10" width="44" height="52" rx="3" className="es-card" />
          <rect x="112" y="10" width="44" height="52" rx="3" className="es-card" />
          <circle cx="26" cy="32" r="9" className="es-a" />
          <path d="M134 25l8 8-8 8-8-8z" className="es-b" />
          <path d="M48 36 C 66 36, 66 36, 80 36 S 94 36, 112 36" className="es-edge" />
          <circle cx="80" cy="36" r="6" className="es-node" />
        </svg>
        <h2 id="empty-title" className="empty-state__title">
          {copy.empty.headline}
        </h2>
        <p className="empty-state__body">{copy.empty.body}</p>
        <Button variant="primary" icon="upload" onClick={async () => onAddFiles(await pickImages(true))}>
          {copy.empty.addImages}
        </Button>
        <p className="empty-state__fine">{copy.empty.accepted}</p>
      </div>
    </section>
  );
}
