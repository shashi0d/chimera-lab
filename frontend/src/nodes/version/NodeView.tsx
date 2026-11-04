import { useState } from "react";
import { NodeCard, type NodeStatus } from "../../canvas/NodeCard";
import { evo } from "../../evo/index";
import { isTerminal, useRun } from "../../evo/runs";
import { useGraph } from "../../graph/store";
import { addCardNode, addEditNode, addFusionFrom, versionNumber } from "../../lab/graph";
import { downloadVersion } from "../../lab/store";
import { IconButton } from "../../ui/Button";
import { Icon } from "../../ui/Icon";
import { Pill } from "../../ui/Pill";
import type { NodeViewProps } from "../types";
import { VERSION_INPUTS, VERSION_OUTPUTS, type VersionConfig, type VersionData } from "./types";

const OPERATION: Record<string, string> = { fusion: "Fusion", revise: "Revise", paint: "Paint" };

/** One image in the creature's path. The tools act on the selected card; edits branch from it to the right. */
export function VersionView({ node, selected }: NodeViewProps<VersionConfig, VersionData>) {
  const { version, runId, error } = node.data;
  const run = useRun(version ? null : runId ?? null);
  const readOnly = useGraph((s) => s.readOnly);
  const n = useGraph(() => versionNumber(node.id));
  const [broken, setBroken] = useState(false);
  const active = !version && Boolean(run && !isTerminal(run.status));
  const runFailed = !version && run && (run.status === "failed" || run.status === "interrupted");
  const latest = run?.images[run.images.length - 1];
  const title = version?.title ?? (run?.sire && run.dam ? `${run.sire.commonName} × ${run.dam.commonName}` : "New creature");

  let status: NodeStatus | undefined;
  if (version?.isFinal) status = { tone: "ok", label: "Final" };
  else if (version) status = undefined;
  else if (error || runFailed) status = { tone: "error", label: "No image" };
  else status = { tone: "running", label: "Generating" };

  const media = version && !broken ? (
    <figure className="plate">
      <div className="plate__frame">
        <img className="plate__img is-loaded" decoding="async" src={evo().imageUrl(version.imageUrl)} alt={`${title}, version ${n}`} draggable={false} onError={() => setBroken(true)} />
      </div>
    </figure>
  ) : active && latest ? (
    <figure className="plate plate--wip">
      <div className="plate__frame">
        <img className="plate__img is-loaded" decoding="async" src={evo().imageUrl(latest.url)} alt={`Latest attempt ${latest.imageId}`} draggable={false} />
      </div>
      <figcaption className="plate__overlay-label plate__wip-label">Latest attempt · the agent is still working</figcaption>
    </figure>
  ) : (
    <div className={`plate ${error || runFailed || broken ? "plate--empty is-muted" : "plate--skeleton"}`} aria-label={error ?? "Generating"}>
      {error || runFailed || broken ? <Icon name="result" size={28} /> : <span className="skeleton skeleton--fill" />}
      <span className="plate__overlay-label">{error ?? (runFailed ? "This run ended without an image." : broken ? "The image didn't load." : "Generating…")}</span>
    </div>
  );

  const label = `${title} V${n}`;
  return (
    <NodeCard
      nodeId={node.id}
      kind="version"
      kicker={`V${n} · ${OPERATION[version?.operation ?? "fusion"]}`}
      title={title}
      status={status}
      inputs={VERSION_INPUTS}
      outputs={VERSION_OUTPUTS}
      media={media}
      selected={selected}
      className={[version?.isFinal ? "is-final" : "", !version ? "is-pending" : ""].filter(Boolean).join(" ")}
      toolbar={
        version && !readOnly ? (
          <>
            <IconButton icon="replace" label="Revise this image" onClick={() => addEditNode(node.id, "revise")} />
            <IconButton icon="brush" label="Paint an area to edit" onClick={() => addEditNode(node.id, "paint")} />
            <IconButton icon="card" label="Animal card" onClick={() => addCardNode(node.id)} />
            <IconButton icon="fusion" label="Fuse with another animal" onClick={() => addFusionFrom(node.id)} />
            <IconButton icon="download" label="Download image" onClick={() => void downloadVersion(version, label)} />
          </>
        ) : null
      }
    >
      {version ? <p className="version-node__instruction">{version.instruction}</p> : null}
      {version?.isFinal || version?.publicationId ? (
        <div className="version-node__pills">
          {version.isFinal ? (
            <Pill tone="brand">
              <Icon name="star" size={12} /> Final
            </Pill>
          ) : null}
          {version.publicationId ? (
            <Pill tone="info">
              <Icon name="globe" size={12} /> In the gallery
            </Pill>
          ) : null}
        </div>
      ) : null}
    </NodeCard>
  );
}
