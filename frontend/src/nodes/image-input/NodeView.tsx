import { useState } from "react";
import { presentError } from "../../api/errorMessages";
import { NodeCard, type NodeStatus } from "../../canvas/NodeCard";
import { pickImages } from "../../canvas/filePicker";
import { replaceImage } from "../../canvas/addImages";
import { copy } from "../../copy";
import { useGraph } from "../../graph/store";
import { Button, IconButton } from "../../ui/Button";
import { Icon } from "../../ui/Icon";
import type { NodeViewProps } from "../types";
import { IMAGE_INPUT_INPUTS, IMAGE_INPUT_OUTPUTS } from "./ports";
import { useSlotOf, useSpecies } from "./species";
import type { ImageInputConfig, ImageInputData } from "./types";
import { cancelUpload, startUpload } from "./uploads";
import { usePreview } from "./usePreview";

const t = copy.nodes.imageInput;

function statusOf(d: ImageInputData): NodeStatus {
  switch (d.upload.status) {
    case "processing":
      return { tone: "running", label: t.processing.replace("…", "") };
    case "uploading":
      return { tone: "running", label: copy.status.uploading };
    case "queued":
      return { tone: "warn", label: copy.status.queued };
    case "error":
      return { tone: "error", label: copy.status.error };
    case "cancelled":
      return { tone: "idle", label: copy.status.cancelled };
    default:
      return d.flagged ? { tone: "error", label: copy.status.error } : { tone: "ok", label: t.ready };
  }
}

/** Image-first: the photo fills the card; the title is the identified species, never the filename. */
export function ImageInputView({ node, selected }: NodeViewProps<ImageInputConfig, ImageInputData>) {
  const d = node.data;
  const preview = usePreview(d);
  const species = useSpecies(d.assetId);
  const slot = useSlotOf(node.id);
  const [broken, setBroken] = useState(false);
  const removeNodes = useGraph((s) => s.removeNodes);
  const readOnly = useGraph((s) => s.readOnly);
  const pct = Math.round(d.upload.progress * 100);
  const err = d.upload.error ? presentError(d.upload.error) : null;
  const flagged = Boolean(d.flagged);

  const replace = async () => {
    const files = await pickImages(false);
    if (files[0]) await replaceImage(node.id, files[0]);
  };

  const media = (
    <div className="image-node__frame">
      {preview && !broken ? (
        <img className="image-node__img" src={preview} alt={t.alt(d.fileName || t.untitled)} draggable={false} onError={() => setBroken(true)} />
      ) : (
        <div className="image-node__placeholder">
          {broken ? <Icon name="image" size={28} /> : <span className="skeleton skeleton--fill" aria-hidden="true" />}
          <span className="image-node__placeholder-label">{broken ? t.broken : t.processing}</span>
        </div>
      )}
      {d.upload.status === "uploading" ? (
        <div className="upload-progress">
          <progress className="upload-progress__bar" max={100} value={pct} aria-label={t.uploading(pct)} />
          <span className="upload-progress__row">
            <span className="upload-progress__label" aria-hidden="true">
              {t.uploading(pct)}
            </span>
            <button type="button" className="link-btn nodrag" onClick={() => cancelUpload(node.id)}>
              {t.cancel}
            </button>
          </span>
        </div>
      ) : null}
      {flagged ? (
        <p className="image-node__banner image-node__banner--error">
          <Icon name="alert" size={14} /> {d.flagged}
        </p>
      ) : d.upload.status === "queued" ? (
        <p className="image-node__banner image-node__banner--warn">
          <Icon name="offline" size={14} /> {t.queued}
        </p>
      ) : d.upload.status === "error" && err ? (
        <div className="image-node__banner image-node__banner--error" role="alert">
          <p className="node__error-title">{err.title}</p>
          {err.fix ? <p className="node__error-fix">{err.fix}</p> : null}
          <div className="node__actions">
            {err.retry ? (
              <Button size="sm" icon="refresh" className="nodrag" onClick={() => void startUpload(node.id)}>
                {t.retry}
              </Button>
            ) : null}
            <Button size="sm" variant="ghost" icon="replace" className="nodrag" onClick={replace}>
              {t.replace}
            </Button>
          </div>
        </div>
      ) : d.upload.status === "cancelled" ? (
        <div className="image-node__banner">
          <p className="node__error-fix">{t.cancelled}</p>
          <div className="node__actions">
            <Button size="sm" icon="upload" className="nodrag" onClick={() => void startUpload(node.id)}>
              {t.retry}
            </Button>
            <Button size="sm" variant="ghost" icon="trash" className="nodrag" onClick={() => removeNodes([node.id])}>
              {t.remove}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );

  return (
    <NodeCard
      nodeId={node.id}
      kind="image-input"
      kicker={t.kicker(slot)}
      title={species ?? t.unknownSpecies}
      status={statusOf(d)}
      inputs={IMAGE_INPUT_INPUTS}
      outputs={IMAGE_INPUT_OUTPUTS}
      selected={selected}
      className={[flagged ? "is-flagged" : "", d.upload.status === "error" ? "node--error" : ""].filter(Boolean).join(" ")}
      media={media}
      toolbar={
        readOnly ? null : (
          <>
            <IconButton icon="replace" label={t.replace} onClick={replace} />
            <IconButton icon="trash" label={t.remove} onClick={() => removeNodes([node.id])} />
          </>
        )
      }
      footer={<p className="image-node__meta">{d.width && d.height ? `${d.width} × ${d.height}` : " "}</p>}
    />
  );
}
