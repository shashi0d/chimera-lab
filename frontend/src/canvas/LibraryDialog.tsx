import { useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";
import { evo } from "../evo/index";
import { labApi, type LabVersion } from "../lab/api";
import { blobUrl, getBlob, photoKeys } from "../persistence/blobStore";
import { Button, IconButton } from "../ui/Button";
import { SegmentedTabs } from "../ui/SegmentedTabs";
import { pickImages } from "./filePicker";

type Tab = "generated" | "photos";

function PhotoThumb({ blobKey, onPick }: { blobKey: string; onPick(): void }) {
  const [url, setUrl] = useState<string | undefined>();
  useEffect(() => {
    let alive = true;
    void blobUrl(blobKey).then((u) => alive && setUrl(u));
    return () => {
      alive = false;
    };
  }, [blobKey]);
  return (
    <li>
      <button type="button" className="library__item" onClick={onPick} disabled={!url}>
        {url ? <img src={url} alt="Your photo" loading="lazy" decoding="async" /> : <span className="skeleton skeleton--fill" />}
      </button>
    </li>
  );
}

/**
 * Add image: everything made so far (generated images, from every workspace) and the photos on this device, plus
 * uploading new ones. A generated image is added as an image card, ready to edit, save or fuse.
 */
export function LibraryDialog({ onClose, onAddFiles, onAddVersion }: {
  onClose(): void;
  onAddFiles(files: File[]): void;
  onAddVersion(v: LabVersion): void;
}) {
  const [tab, setTab] = useState<Tab>("generated");
  const [versions, setVersions] = useState<LabVersion[] | null>(null);
  const [photos, setPhotos] = useState<string[] | null>(null);
  const titleId = useId();

  useEffect(() => {
    let alive = true;
    labApi
      .versions()
      .then((list) => alive && setVersions([...list].reverse()))
      .catch(() => alive && setVersions([]));
    void photoKeys().then((k) => alive && setPhotos(k));
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => {
      alive = false;
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  const upload = async () => {
    const files = await pickImages(true);
    if (files.length) {
      onAddFiles(files);
      onClose();
    }
  };
  const addPhoto = async (key: string) => {
    const blob = await getBlob(key);
    if (!blob) return;
    onAddFiles([new File([blob], `photo.${blob.type === "image/png" ? "png" : "jpg"}`, { type: blob.type || "image/jpeg" })]);
    onClose();
  };

  const list = tab === "generated" ? versions : photos;
  return createPortal(
    <div className="dialog-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="dialog library" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <header className="dialog__head">
          <h2 id={titleId}>Add an image</h2>
          <IconButton icon="close" label="Close" onClick={onClose} />
        </header>
        <div className="library__bar">
          <SegmentedTabs
            label="Images"
            value={tab}
            onChange={(v) => setTab(v as Tab)}
            items={[
              { value: "generated", label: `Made in the Lab${versions ? ` (${versions.length})` : ""}` },
              { value: "photos", label: `Your photos${photos ? ` (${photos.length})` : ""}` },
            ]}
          />
          <Button variant="primary" icon="upload" onClick={() => void upload()}>
            Upload from device
          </Button>
        </div>
        {list === null ? <span className="spinner" aria-label="Loading images" /> : null}
        {list && !list.length ? (
          <p className="tools__note">{tab === "generated" ? "Nothing made yet. Make a creature with a Fusion first." : "No photos on this device yet. Upload one."}</p>
        ) : null}
        <ul className="library__grid">
          {tab === "generated"
            ? versions?.map((v) => (
                <li key={v.id}>
                  <button
                    type="button"
                    className="library__item"
                    onClick={() => {
                      onAddVersion(v);
                      onClose();
                    }}
                  >
                    <img src={evo().imageUrl(v.imageUrl)} alt={v.title ?? "Generated creature"} loading="lazy" decoding="async" />
                    <span className="library__label">{v.title ?? "Untitled"}</span>
                  </button>
                </li>
              ))
            : photos?.map((k) => <PhotoThumb key={k} blobKey={k} onPick={() => void addPhoto(k)} />)}
        </ul>
      </div>
    </div>,
    document.body,
  );
}
