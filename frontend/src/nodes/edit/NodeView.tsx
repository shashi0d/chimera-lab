import { useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";
import { NodeCard, type NodeStatus } from "../../canvas/NodeCard";
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
import { EDIT_INPUTS, EDIT_OUTPUTS, maskKey, type EditConfig, type EditData, type EditOperation } from "./types";

function PaintDialog({ imageUrl, onSave, onClose }: { imageUrl: string; onSave: (mask: Blob) => void; onClose: () => void }) {
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
          <h2 id={titleId}>Paint the area to change</h2>
          <IconButton icon="close" label="Close" onClick={onClose} />
        </header>
        <PaintEditor imageUrl={imageUrl} disabled={false} onSave={onSave} />
      </div>
    </div>,
    document.body,
  );
}

function MaskPreview({ nodeId, imageUrl }: { nodeId: string; imageUrl: string }) {
  const [url, setUrl] = useState<string | undefined>();
  const has = useGraph((s) => Boolean((s.nodes.find((n) => n.id === nodeId)?.data as EditData | undefined)?.hasMask));
  useEffect(() => {
    let alive = true;
    if (has) void blobUrl(maskKey(nodeId)).then((u) => alive && setUrl(u));
    else setUrl(undefined);
    return () => {
      alive = false;
    };
  }, [has, nodeId]);
  if (!has || !url) return null;
  return (
    <div className="edit-node__mask" aria-label="Painted area">
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

  const setConfig = (patch: Partial<EditConfig>) => useGraph.getState().updateNodeConfig<EditConfig>(node.id, (c) => ({ ...c, ...patch }));
  const saveMask = async (mask: Blob) => {
    await deleteBlob(maskKey(node.id)).catch(() => undefined);
    await putBlob(maskKey(node.id), mask);
    useGraph.getState().updateNodeData<EditData>(node.id, (d) => ({ ...d, hasMask: true, error: null }));
    setPainting(false);
  };

  let status: NodeStatus | undefined;
  if (running) status = { tone: "running", label: job?.stage ?? "Starting" };
  else if (error) status = { tone: "error", label: "Failed" };
  else if (made) status = { tone: "ok", label: made === 1 ? "1 image" : `${made} images` };

  return (
    <NodeCard
      nodeId={node.id}
      kind="edit"
      kicker={`Edit · ${operation === "paint" ? "Paint" : "Revise"}`}
      title={operation === "paint" ? "Change a painted area" : "Change the image"}
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
            disabled={readOnly || running || blocking.length > 0 || !parent}
            onClick={() => void generateEdit(node.id)}
          >
            {running ? job?.stage ?? "Starting…" : made ? "Generate another" : "Generate"}
          </Button>
          {blocking[0] && !running ? <p className="edit-node__hint">{blocking[0].message}</p> : null}
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
        ]}
      />
      <label className="edit-node__label" htmlFor={fieldId}>
        {operation === "paint" ? "What should change in the painted area?" : "What should change?"}
      </label>
      <textarea
        id={fieldId}
        className="text-input edit-node__text nodrag nowheel"
        rows={3}
        maxLength={2000}
        value={instruction}
        disabled={readOnly || running}
        placeholder={operation === "paint" ? "Blend the waist into the abdomen" : "Make the legs longer, keep the face"}
        onChange={(e) => setConfig({ instruction: e.target.value })}
        onKeyDown={(e) => {
          e.stopPropagation();
          if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && !running && !blocking.length) void generateEdit(node.id);
        }}
      />
      {operation === "paint" && parent ? (
        <div className="edit-node__paint">
          <MaskPreview nodeId={node.id} imageUrl={parent.imageUrl} />
          <Button size="sm" icon="brush" className="nodrag" disabled={readOnly || running} onClick={() => setPainting(true)}>
            {node.data.hasMask ? "Repaint area" : "Paint area"}
          </Button>
        </div>
      ) : null}
      {error ? (
        <p className="edit-node__error" role="alert">
          <Icon name="alert" size={14} /> {error}
        </p>
      ) : null}
      {jobIds.length > 0 && !running && !error ? <p className="edit-node__meta">Each run adds an image to the right. Change the text and generate again to explore.</p> : null}
      {painting && parent ? <PaintDialog imageUrl={parent.imageUrl} onSave={(m) => void saveMask(m)} onClose={() => setPainting(false)} /> : null}
    </NodeCard>
  );
}
