import { useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";
import { NodeCard, type NodeStatus } from "../../canvas/NodeCard";
import { useImages } from "../../evo/data";
import { evo } from "../../evo/index";
import { useGraph } from "../../graph/store";
import { parentVersionOf } from "../../lab/graph";
import { PaintEditor } from "../../lab/PaintEditor";
import { generateEdit, useLab } from "../../lab/store";
import { blobUrl, deleteBlob, putBlob } from "../../persistence/blobStore";
import { Button, IconButton } from "../../ui/Button";
import { Icon } from "../../ui/Icon";
import { SegmentedTabs } from "../../ui/SegmentedTabs";
import type { NodeViewProps } from "../types";
import { EDIT_INPUTS, EDIT_OUTPUTS, maskKey, sketchKey, type EditConfig, type EditData, type EditOperation } from "./types";

function PaintDialog({ imageUrl, onSave, onClose, mode = "mask" }: { imageUrl: string; onSave: (mask: Blob) => void; onClose: () => void; mode?: "mask" | "sketch" }) {
  const titleId = useId();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return createPortal(
    <div className="dialog-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="dialog paint-dialog" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <header className="dialog__head">
          <h2 id={titleId}>{mode === "sketch" ? "Draw what you want" : "Paint the area to change"}</h2>
          <IconButton icon="close" label="Close" onClick={onClose} />
        </header>
        <PaintEditor imageUrl={imageUrl} disabled={false} onSave={onSave} mode={mode} />
      </div>
    </div>,
    document.body,
  );
}

function MaskPreview({ nodeId, imageUrl, sketch = false }: { nodeId: string; imageUrl: string; sketch?: boolean }) {
  const [url, setUrl] = useState<string | undefined>();
  const has = useGraph((s) => {
    const d = s.nodes.find((n) => n.id === nodeId)?.data as EditData | undefined;
    return Boolean(sketch ? d?.hasSketch : d?.hasMask);
  });
  useEffect(() => {
    let alive = true;
    if (has) void blobUrl(sketch ? sketchKey(nodeId) : maskKey(nodeId)).then((u) => alive && setUrl(u));
    else setUrl(undefined);
    return () => {
      alive = false;
    };
  }, [has, nodeId, sketch]);
  if (!has || !url) return null;
  return (
    <div className={`edit-node__mask${sketch ? " edit-node__mask--sketch" : ""}`} aria-label={sketch ? "Your drawing" : "Painted area"}>
      <img src={evo().imageUrl(imageUrl)} alt="" draggable={false} />
      <img className="edit-node__mask-paint" src={url} alt="" draggable={false} />
    </div>
  );
}

/** One change to the connected image: Revise (whole image) or Paint (only a painted area). */
export function EditView({ node, selected, issues }: NodeViewProps<EditConfig, EditData>) {
  const { operation, instruction } = node.config;
  const { activeJobId, error, jobIds } = node.data;
  const job = useLab((s) => (activeJobId ? s.jobs[activeJobId] : undefined));
  const starting = useLab((s) => Boolean(s.starting[node.id]));
  const readOnly = useGraph((s) => s.readOnly);
  const parent = useGraph(() => parentVersionOf(node.id)?.version ?? null);
  const made = useGraph((s) => s.edges.filter((e) => e.source === node.id).length);
  const [painting, setPainting] = useState(false);
  const fieldId = useId();
  const running = starting || Boolean(activeJobId);
  const blocking = issues.filter((i) => i.severity === "block");
  const { out: outOfImages } = useImages();
  const hint = blocking[0]?.message ?? (outOfImages ? "You've used all your images, so you can't make new edits." : null);

  const setConfig = (patch: Partial<EditConfig>) => useGraph.getState().updateNodeConfig<EditConfig>(node.id, (c) => ({ ...c, ...patch }));
  const saveMask = async (mask: Blob) => {
    const sketching = operation === "sketch";
    const key = sketching ? sketchKey(node.id) : maskKey(node.id);
    await deleteBlob(key).catch(() => undefined);
    await putBlob(key, mask);
    useGraph.getState().updateNodeData<EditData>(node.id, (d) => ({ ...d, ...(sketching ? { hasSketch: true } : { hasMask: true }), error: null }));
    setPainting(false);
  };
  const KIND: Record<EditOperation, string> = { revise: "Revise", paint: "Paint", sketch: "Draw" };

  let status: NodeStatus | undefined;
  if (running) status = { tone: "running", label: job?.stage ?? "Starting" };
  else if (error) status = { tone: "error", label: "Failed" };
  else if (made) status = { tone: "ok", label: made === 1 ? "1 image" : `${made} images` };

  return (
    <NodeCard
      nodeId={node.id}
      kind="edit"
      kicker={`Edit · ${KIND[operation]}`}
      title={operation === "paint" ? "Change a painted area" : operation === "sketch" ? "Draw what you want" : "Change the image"}
      status={status}
      inputs={EDIT_INPUTS}
      outputs={EDIT_OUTPUTS}
      selected={selected}
      className={[running ? "is-generating" : "", error ? "node--error" : ""].filter(Boolean).join(" ")}
      toolbar={readOnly ? null : <IconButton icon="trash" label="Remove this edit" onClick={() => useGraph.getState().removeNodes([node.id])} />}
      footer={
        <div className="edit-node__actions">
          <Button
            variant="primary"
            icon={made ? "refresh" : "fusion"}
            busy={running}
            className="nodrag"
            disabled={readOnly || running || blocking.length > 0 || !parent || outOfImages}
            onClick={() => void generateEdit(node.id)}
          >
            {running ? job?.stage ?? "Starting…" : made ? "Generate another" : "Generate"}
          </Button>
          {hint && !running ? <p className="edit-node__hint">{hint}</p> : null}
        </div>
      }
    >
      <SegmentedTabs
        label="Kind of edit"
        value={operation}
        onChange={(v) => setConfig({ operation: v as EditOperation })}
        items={[
          { value: "revise", label: "Revise" },
          { value: "paint", label: "Paint area" },
          { value: "sketch", label: "Draw" },
        ]}
      />
      <label className="edit-node__label" htmlFor={fieldId}>
        {operation === "paint" ? "What should change in the painted area?" : operation === "sketch" ? "Anything to add about your drawing? (optional)" : "What should change?"}
      </label>
      <textarea
        id={fieldId}
        className="text-input edit-node__text nodrag nowheel"
        rows={3}
        maxLength={2000}
        value={instruction}
        disabled={readOnly || running}
        placeholder={operation === "paint" ? "Blend the waist into the abdomen" : operation === "sketch" ? "A curved horn, bone white" : "Make the legs longer, keep the face"}
        onChange={(e) => setConfig({ instruction: e.target.value })}
        onKeyDown={(e) => {
          e.stopPropagation();
          if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && !running && !blocking.length) void generateEdit(node.id);
        }}
      />
      {(operation === "paint" || operation === "sketch") && parent ? (
        <div className="edit-node__paint">
          <MaskPreview nodeId={node.id} imageUrl={parent.imageUrl} sketch={operation === "sketch"} />
          <Button size="sm" icon="brush" className="nodrag" disabled={readOnly || running} onClick={() => setPainting(true)}>
            {operation === "sketch" ? (node.data.hasSketch ? "Draw again" : "Draw on the image") : node.data.hasMask ? "Repaint area" : "Paint area"}
          </Button>
        </div>
      ) : null}
      {error ? (
        <p className="edit-node__error" role="alert">
          <Icon name="alert" size={14} /> {error}
        </p>
      ) : null}
      {jobIds.length > 0 && !running && !error ? <p className="edit-node__meta">Each run adds an image to the right. Change the text and generate again to explore.</p> : null}
      {painting && parent ? <PaintDialog imageUrl={parent.imageUrl} mode={operation === "sketch" ? "sketch" : "mask"} onSave={(m) => void saveMask(m)} onClose={() => setPainting(false)} /> : null}
    </NodeCard>
  );
}
