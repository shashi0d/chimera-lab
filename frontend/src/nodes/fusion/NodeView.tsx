import { useState } from "react";
import { presentError } from "../../api/errorMessages";
import { NodeCard, type NodeStatus } from "../../canvas/NodeCard";
import { ErrorBlock, StepList, totalMs, useCountdown } from "../../canvas/RunParts";
import { formatElapsed, formatSeconds, useNow } from "../../canvas/useNow";
import { useConnectivity } from "../../connectivity/store";
import { copy } from "../../copy";
import { upstreamNode } from "../../graph/queries";
import { useGraph } from "../../graph/store";
import { useRuns } from "../../runs/store";
import { TERMINAL } from "../../runs/transport";
import type { Run } from "../../types/api";
import { Button, IconButton } from "../../ui/Button";
import { Icon } from "../../ui/Icon";
import type { ImageInputData } from "../image-input/types";
import { speciesFor, useSpecies } from "../image-input/species";
import { usePreview } from "../image-input/usePreview";
import type { NodeViewProps } from "../types";
import { BodyDiagram, resetDonors } from "./BodyDiagram";
import { FUSION_INPUTS, FUSION_OUTPUTS } from "./ports";
import { PARTS, readDonors, type FusionConfig, type FusionData } from "./types";

const t = copy.nodes.fusion;
const LONG_WAIT_MS = 20_000;
const VERY_LONG_WAIT_MS = 120_000;

function fusionStatus(run: Run | undefined, starting: boolean, stale: boolean, blocked: boolean): NodeStatus {
  if (starting) return { tone: "running", label: copy.status.queued };
  if (!run) return blocked ? { tone: "idle", label: copy.status.idle } : { tone: "idle", label: copy.status.ready };
  switch (run.status) {
    case "queued":
      return { tone: "running", label: copy.status.queued };
    case "running":
      return { tone: "running", label: copy.status.running };
    case "succeeded":
      return stale ? { tone: "stale", label: copy.status.stale } : { tone: "ok", label: copy.status.succeeded };
    case "failed":
      return { tone: "error", label: copy.status.failed };
    case "cancelled":
      return { tone: "idle", label: copy.status.cancelled };
    case "interrupted":
      return { tone: "error", label: copy.status.interrupted };
  }
}

/** Upstream image for one slot: node, preview URL and identified species. */
function useSlot(fusionId: string, port: "a" | "b") {
  const nodes = useGraph((s) => s.nodes);
  const edges = useGraph((s) => s.edges);
  const up = upstreamNode({ nodes, edges }, fusionId, port);
  const data = up?.data as ImageInputData | undefined;
  const preview = usePreview(data ?? {});
  const species = useSpecies(data?.assetId);
  return { up, preview, species };
}

/** Small portrait + species name for one parent (no form controls on the card). */
function DonorPortrait({ slot, preview, species, connected }: { slot: "A" | "B"; preview?: string; species: string | null; connected: boolean }) {
  return (
    <div className={`donor-chip donor-chip--${slot.toLowerCase()}${connected ? "" : " is-empty"}`}>
      <span className="donor-chip__portrait" aria-hidden="true">
        {preview ? <img src={preview} alt="" draggable={false} /> : <Icon name="image" size={16} />}
        <span className="donor-chip__letter">{slot}</span>
      </span>
      <span className="donor-chip__text">
        <span className="sr-only">{t.slot(slot)}: </span>
        <span className="donor-chip__name">{connected ? (species ?? copy.nodes.imageInput.title(slot)) : t.empty}</span>
      </span>
    </div>
  );
}

/** Toolbar slot selector: the keyboard path for wiring A and B. */
function SlotSelect({ fusionId, port, disabled }: { fusionId: string; port: "a" | "b"; disabled: boolean }) {
  const nodes = useGraph((s) => s.nodes);
  const edges = useGraph((s) => s.edges);
  const runs = useRuns((s) => s.runs);
  const up = upstreamNode({ nodes, edges }, fusionId, port);
  const images = nodes.filter((n) => n.type === "image-input");
  const slot = port.toUpperCase();
  const selectId = `${fusionId}-slot-${port}`;

  const connect = (sourceId: string) => {
    const g = useGraph.getState();
    const existing = g.edges.find((e) => e.target === fusionId && e.targetPort === port);
    g.checkpoint();
    useGraph.setState((s) => ({
      edges: [
        ...s.edges.filter((e) => e !== existing),
        ...(sourceId
          ? [
              {
                id: `e-${port}-${fusionId}-${Date.now().toString(36)}`,
                source: sourceId,
                sourcePort: "out",
                target: fusionId,
                targetPort: port,
              },
            ]
          : []),
      ],
      revision: s.revision + 1,
    }));
    if (existing?.source !== sourceId) g.markDownstreamStale(fusionId);
  };

  return (
    <span className="slot-select">
      <span className="slot-select__letter" aria-hidden="true">
        {slot}
      </span>
      <select
        id={selectId}
        aria-label={t.connectVia(slot)}
        className="slot-select__select"
        value={up?.id ?? ""}
        disabled={disabled}
        onChange={(e) => connect(e.target.value)}
      >
        <option value="">{up ? t.empty : t.chooseImage}</option>
        {images.map((img, i) => {
          const d = img.data as ImageInputData;
          const name = speciesFor(d.assetId, runs, nodes) ?? copy.nodes.imageInput.unknownSpecies;
          return (
            <option key={img.id} value={img.id}>
              {`${i + 1}. ${name}`}
            </option>
          );
        })}
      </select>
    </span>
  );
}

function swapSlots(fusionId: string): void {
  const g = useGraph.getState();
  g.checkpoint();
  useGraph.setState((s) => ({
    edges: s.edges.map((e) =>
      e.target === fusionId && (e.targetPort === "a" || e.targetPort === "b") ? { ...e, targetPort: e.targetPort === "a" ? "b" : "a" } : e,
    ),
    revision: s.revision + 1,
  }));
  g.markDownstreamStale(fusionId);
}

export function FusionView({ node, selected, issues }: NodeViewProps<FusionConfig, FusionData>) {
  const runId = node.data.activeRunId ?? null;
  const run = useRuns((s) => (runId ? s.runs[runId] : undefined));
  const starting = useRuns((s) => Boolean(s.starting[node.id]));
  const startError = useRuns((s) => s.startErrors[node.id]);
  const start = useRuns((s) => s.start);
  const cancel = useRuns((s) => s.cancel);
  const readOnly = useGraph((s) => s.readOnly);
  const connectivity = useConnectivity((s) => s.status);
  const [cancelling, setCancelling] = useState(false);
  const slotA = useSlot(node.id, "a");
  const slotB = useSlot(node.id, "b");
  const donors = readDonors(node.config);
  const pinned = PARTS.some((p) => donors[p] !== "auto");

  const active = starting || (run !== undefined && !TERMINAL.has(run.status));
  const now = useNow(active, 500);
  const elapsed = run ? now - Date.parse(run.createdAt) : 0;
  const blocking = issues.filter((i) => i.severity === "block");
  const advisory = issues.filter((i) => i.severity === "warn");
  const stale = Boolean(node.data.stale);
  const status = fusionStatus(run, starting, stale, blocking.length > 0);
  const runError = run && (run.status === "failed" || run.status === "interrupted") ? run.error : null;
  const shownError = startError ?? runError ?? null;

  const fuse = () => {
    setCancelling(false);
    void start(node.id);
  };
  const countdown = useCountdown(shownError, fuse);

  const doCancel = async () => {
    setCancelling(true);
    await cancel(node.id);
    setCancelling(false);
  };

  const fuseLabel = shownError && presentError(shownError).retry ? t.retry : run?.status === "succeeded" ? t.fuseAgain : t.fuse;
  const paused = active && connectivity !== "online";

  return (
    <NodeCard
      nodeId={node.id}
      kind="fusion"
      kicker={t.kicker}
      title={t.title}
      status={status}
      inputs={FUSION_INPUTS}
      outputs={FUSION_OUTPUTS}
      selected={selected}
      className={[active ? "is-running" : "", shownError ? "node--error" : "", stale ? "is-stale" : ""].filter(Boolean).join(" ")}
      toolbar={
        readOnly ? null : (
          <>
            <SlotSelect fusionId={node.id} port="a" disabled={active} />
            <SlotSelect fusionId={node.id} port="b" disabled={active} />
            <IconButton icon="replace" label={t.swap} disabled={active || !(slotA.up || slotB.up)} onClick={() => swapSlots(node.id)} />
            <IconButton icon="refresh" label={t.resetAnatomy} disabled={active || !pinned} onClick={() => resetDonors(node.id)} />
          </>
        )
      }
      footer={
        <>
          {active ? (
            <Button
              variant={elapsed > VERY_LONG_WAIT_MS ? "danger" : "ghost"}
              size="sm"
              icon="stop"
              className="nodrag"
              busy={cancelling}
              disabled={cancelling || !runId}
              onClick={doCancel}
            >
              {cancelling ? t.cancelling : t.cancel}
            </Button>
          ) : (
            <Button
              variant="primary"
              icon="fusion"
              className="nodrag fusion-node__fuse"
              disabled={blocking.length > 0 || starting || countdown !== null}
              aria-describedby={blocking.length ? `${node.id}-hint` : undefined}
              onClick={fuse}
            >
              {fuseLabel}
            </Button>
          )}
          {active ? (
            <span className="node__timer" aria-label={`${t.elapsed} ${formatElapsed(elapsed)}`}>
              {formatElapsed(elapsed)}
            </span>
          ) : null}
        </>
      }
    >
      <div className="fusion-node__parents">
        <DonorPortrait slot="A" preview={slotA.preview} species={slotA.species} connected={Boolean(slotA.up)} />
        <span className="fusion-node__times" aria-hidden="true">
          ×
        </span>
        <DonorPortrait slot="B" preview={slotB.preview} species={slotB.species} connected={Boolean(slotB.up)} />
      </div>
      {active ? null : (
        <BodyDiagram
          nodeId={node.id}
          config={node.config}
          disabled={readOnly || active}
          faces={{
            A: { preview: slotA.preview, name: slotA.species ?? "A" },
            B: { preview: slotB.preview, name: slotB.species ?? "B" },
          }}
        />
      )}
      {run && active ? <StepList steps={run.steps} now={now} /> : null}
      <div className="fusion-node__messages" aria-live="polite">
        {!active && blocking[0] ? (
          <p id={`${node.id}-hint`} className="node__hint">
            <Icon name="info" size={14} /> {blocking[0].message}
          </p>
        ) : !active && advisory[0] ? (
          <p className="node__hint node__hint--warn">
            <Icon name="alert" size={14} /> {advisory[0].message}
          </p>
        ) : null}
        {stale && !active && run?.status === "succeeded" ? (
          <p className="node__note node__note--warn">
            <Icon name="refresh" size={14} /> {t.stale}
          </p>
        ) : null}
        {paused ? (
          <p className="node__note node__note--warn">
            <Icon name="offline" size={14} /> {t.pausedOffline}
          </p>
        ) : active && elapsed > VERY_LONG_WAIT_MS ? (
          <p className="node__note node__note--warn">{t.veryLongWait}</p>
        ) : active && elapsed > LONG_WAIT_MS ? (
          <p className="node__note node__note--warn">{t.longWait}</p>
        ) : null}
        {!active && shownError ? <ErrorBlock err={shownError} countdown={countdown} /> : null}
      </div>
      {run && !active ? (
        // Finished (any outcome): the step log folds away so the outcome and the next action lead.
        <details className="steps-details">
          <summary className="steps-details__summary nodrag">
            {t.showSteps}
            <span className="steps-details__meta">{t.summary(run.steps.length, formatSeconds(totalMs(run.steps)))}</span>
          </summary>
          <StepList steps={run.steps} now={now} allDetails />
        </details>
      ) : null}
    </NodeCard>
  );
}
