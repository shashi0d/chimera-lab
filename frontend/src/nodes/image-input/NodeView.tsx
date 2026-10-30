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

export function ImageInputView({ node, selected, catalog }: NodeViewProps<ImageInputConfig, ImageInputData>) {
  const d = node.data;
  const preview = usePreview(d);
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

  return (
    <NodeCard
      nodeId={node.id}
      kind="image-input"
      catalog={catalog}
      title={d.fileName || t.untitled}
      icon="image"
      status={statusOf(d)}
      inputs={IMAGE_INPUT_INPUTS}
      outputs={IMAGE_INPUT_OUTPUTS}
      selected={selected}
      className={[flagged ? "is-flagged" : "", d.upload.status === "error" ? "node--error" : ""].filter(Boolean).join(" ")}
      toolbar={
        readOnly ? null : (
          <>
            <IconButton icon="replace" label={t.replace} onClick={replace} />
            <IconButton icon="trash" label={t.remove} onClick={() => removeNodes([node.id])} />
          </>
        )
      }
    >
      <div className="image-node__frame">
        {preview && !broken ? (
          <img className="image-node__img" src={preview} alt={t.alt(d.fileName || t.untitled)} draggable={false} onError={() => setBroken(true)} />
        ) : (
          <div className="image-node__placeholder">
            <Icon name="image" size={28} />
            <span>{broken ? t.broken : t.processing}</span>
          </div>
        )}
        {d.upload.status === "uploading" ? (
          <div className="upload-progress">
            <progress className="upload-progress__bar" max={100} value={pct} aria-label={t.uploading(pct)} />
            <span className="upload-progress__label" aria-hidden="true">
              {t.uploading(pct)}
            </span>
          </div>
        ) : null}
      </div>
      {flagged ? (
        <p className="node__note node__note--error">
          <Icon name="alert" size={14} /> {d.flagged}
        </p>
      ) : null}
      {d.upload.status === "queued" ? (
        <p className="node__note node__note--warn">
          <Icon name="offline" size={14} /> {t.queued}
        </p>
      ) : null}
      {d.upload.status === "uploading" ? (
        <Button size="sm" variant="ghost" icon="stop" className="nodrag" onClick={() => cancelUpload(node.id)}>
          {t.cancel}
        </Button>
      ) : null}
      {d.upload.status === "error" && err ? (
        <div className="node__error" role="alert">
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
      ) : null}
      {d.upload.status === "cancelled" ? (
        <div className="node__actions">
          <Button size="sm" icon="upload" className="nodrag" onClick={() => void startUpload(node.id)}>
            {t.retry}
          </Button>
          <Button size="sm" variant="ghost" icon="trash" className="nodrag" onClick={() => removeNodes([node.id])}>
            {t.remove}
          </Button>
        </div>
      ) : null}
      {d.upload.status === "done" && d.width ? (
        <p className="image-node__meta">
          {d.width} × {d.height}
        </p>
      ) : null}
    </NodeCard>
  );
}
