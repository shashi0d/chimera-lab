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
import { displaySpecies, useSlotOf } from "./species";
import type { ImageInputConfig, ImageInputData } from "./types";
import { usePreview } from "./usePreview";

const t = copy.nodes.imageInput;

function statusOf(d: ImageInputData): NodeStatus {
  if (d.status === "processing") return { tone: "running", label: t.processing.replace("…", "") };
  if (d.status === "error" || d.flagged) return { tone: "error", label: copy.status.error };
  return { tone: "ok", label: t.ready };
}

/** Image-first: the photo fills the card; the title is the identified species, never the filename. */
export function ImageInputView({ node, selected }: NodeViewProps<ImageInputConfig, ImageInputData>) {
  const d = node.data;
  const preview = usePreview(d);
  const slot = useSlotOf(node.id);
  const [broken, setBroken] = useState(false);
  const removeNodes = useGraph((s) => s.removeNodes);
  const readOnly = useGraph((s) => s.readOnly);
  const err = d.error ? presentError(d.error) : null;
  const flagged = Boolean(d.flagged);

  const replace = async () => {
    const files = await pickImages(false);
    if (files[0]) await replaceImage(node.id, files[0]);
  };

  const media = (
    <div className="image-node__frame">
      {preview && !broken ? (
        <img className="image-node__img" decoding="async" src={preview} alt={t.alt(d.fileName || t.untitled)} draggable={false} onError={() => setBroken(true)} />
      ) : (
        <div className="image-node__placeholder">
          {broken || d.status === "error" ? <Icon name="image" size={28} /> : <span className="skeleton skeleton--fill" aria-hidden="true" />}
          <span className="image-node__placeholder-label">{broken || d.status === "error" ? t.broken : t.processing}</span>
        </div>
      )}
      {flagged ? (
        <div className="image-node__banner image-node__banner--error" role="alert">
          <p className="node__error-fix">
            <Icon name="alert" size={14} /> {d.flagged}
          </p>
          <div className="node__actions">
            <Button size="sm" variant="ghost" icon="replace" className="nodrag" onClick={replace}>
              {t.replace}
            </Button>
          </div>
        </div>
      ) : d.status === "error" && err ? (
        <div className="image-node__banner image-node__banner--error" role="alert">
          <p className="node__error-title">{err.title}</p>
          {err.fix ? <p className="node__error-fix">{err.fix}</p> : null}
          <div className="node__actions">
            <Button size="sm" variant="ghost" icon="replace" className="nodrag" onClick={replace}>
              {t.replace}
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
      title={displaySpecies(d.species) ?? t.unknownSpecies}
      status={statusOf(d)}
      inputs={IMAGE_INPUT_INPUTS}
      outputs={IMAGE_INPUT_OUTPUTS}
      selected={selected}
      className={[flagged ? "is-flagged" : "", d.status === "error" ? "node--error" : ""].filter(Boolean).join(" ")}
      media={media}
      toolbar={
        readOnly ? null : (
          <>
            <IconButton icon="replace" label={t.replace} onClick={replace} />
            <IconButton icon="trash" label={t.remove} onClick={() => removeNodes([node.id])} />
          </>
        )
      }
      footer={<p className="image-node__meta">{d.width && d.height ? `${d.width} × ${d.height}` : t.onDevice}</p>}
    />
  );
}
