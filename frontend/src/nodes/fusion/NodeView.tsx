import { useId } from "react";
import { presentError } from "../../api/errorMessages";
import { NodeCard, type NodeStatus } from "../../canvas/NodeCard";
import { ErrorBlock, useCountdown } from "../../canvas/RunParts";
import { formatElapsed, useNow } from "../../canvas/useNow";
import { useConnectivity } from "../../connectivity/store";
import { copy } from "../../copy";
import { useCapped } from "../../evo/data";
import { isTerminal, useRun, type DerivedRun } from "../../evo/runs";
import { evo } from "../../evo/index";
import { STYLES, type Style } from "../../evo/types";
import { upstreamNode } from "../../graph/queries";
import { useGraph } from "../../graph/store";
import { Button, IconButton } from "../../ui/Button";
import { Icon } from "../../ui/Icon";
import { SegmentedTabs } from "../../ui/SegmentedTabs";
import { displaySpecies } from "../image-input/species";
import type { ImageInputData } from "../image-input/types";
import type { VersionData } from "../version/types";
import { usePreview } from "../image-input/usePreview";
import type { NodeViewProps } from "../types";
import { FUSION_INPUTS, FUSION_OUTPUTS } from "./ports";
import { startFusion, useFusionStart } from "./start";
import { readStyle, type FusionConfig, type FusionData } from "./types";
import { useWorkspaces } from "../../persistence/workspaces";
import { TUTORIAL_WS } from "../../tutorial/sandbox";

const t = copy.nodes.fusion;

export function runStatus(run: DerivedRun | null, starting: boolean): NodeStatus | null {
  if (starting) return { tone: "running", label: copy.status.starting };
  if (!run) return null;
  switch (run.status) {
    case "loading":
      return { tone: "running", label: copy.status.connecting };
    case "queued":
      return { tone: "warn", label: run.position ? copy.run.queuedShort(run.position) : copy.status.queued };
    case "running":
      return { tone: "running", label: copy.status.running };
    case "succeeded":
      return { tone: "ok", label: copy.status.succeeded };
    case "failed":
      return { tone: "error", label: copy.status.failed };
    case "interrupted":
      return { tone: "error", label: copy.status.interrupted };
  }
}

/** Upstream input for one slot: a photo (preview, identified species) or an earlier creature (its image and title). */
function useSlot(fusionId: string, port: "a" | "b") {
  // Select only the upstream node's type and data (stable while nodes are dragged), never the whole graph.
  const upType = useGraph((s) => upstreamNode(s, fusionId, port)?.type ?? null);
  const upData = useGraph((s) => upstreamNode(s, fusionId, port)?.data ?? null);
  const isVersion = upType === "version";
  const data = !isVersion ? (upData as ImageInputData | null) ?? undefined : undefined;
  const photoPreview = usePreview(data ?? {});
  const version = isVersion ? (upData as VersionData | null)?.version ?? null : null;
  const up = upType !== null;
  if (isVersion) return { up, isVersion, preview: version ? evo().imageUrl(version.imageUrl) : null, species: version?.title ?? null };
  return { up, isVersion, preview: photoPreview, species: displaySpecies(data?.species) };
}

/** One parent: the connected photo with its identified name, or a name field (the contract's fallback). */
function ParentSlot({ nodeId, port, name, disabled }: { nodeId: string; port: "a" | "b"; name: string; disabled: boolean }) {
  const slot = port.toUpperCase() as "A" | "B";
  const { up, isVersion, preview, species } = useSlot(nodeId, port);
  const inputId = useId();
  const setName = (v: string) =>
    useGraph.getState().updateNodeData<FusionData>(nodeId, (d) => ({ ...d, names: { ...(d.names ?? { a: "", b: "" }), [port]: v } }));
  if (up) {
    return (
      <div className={`donor-chip donor-chip--${port}`}>
        <span className="donor-chip__portrait" aria-hidden="true">
          {preview ? <img src={preview} alt="" draggable={false} /> : <Icon name="image" size={16} />}
          <span className="donor-chip__letter">{slot}</span>
        </span>
        <span className="donor-chip__text">
          <span className="sr-only">{t.slot(slot)}: </span>
          <span className="donor-chip__name">{species ?? t.photo}</span>
          <span className="donor-chip__meta">{isVersion ? t.earlierCreature : species ? t.identified : t.identifiedOnRun}</span>
        </span>
      </div>
    );
  }
  return (
    <div className={`donor-chip donor-chip--${port} donor-chip--typed`}>
      <span className="donor-chip__portrait" aria-hidden="true">
        <Icon name="leaf" size={16} />
        <span className="donor-chip__letter">{slot}</span>
      </span>
      <span className="donor-chip__field">
        <label className="donor-chip__label" htmlFor={inputId}>
          {t.nameLabel(slot)}
        </label>
        <input
          id={inputId}
          className="text-input nodrag"
          value={name}
          maxLength={60}
          placeholder={t.namePlaceholder(slot)}
          autoComplete="off"
          spellCheck={false}
          disabled={disabled}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.stopPropagation()}
        />
      </span>
    </div>
  );
}

function swapSlots(fusionId: string): void {
  const g = useGraph.getState();
  g.checkpoint();
  useGraph.setState((s) => ({
    edges: s.edges.map((e) =>
      e.target === fusionId && (e.targetPort === "a" || e.targetPort === "b") ? { ...e, targetPort: e.targetPort === "a" ? "b" : "a" } : e,
    ),
    nodes: s.nodes.map((n) => {
      if (n.id !== fusionId) return n;
      const names = (n.data as FusionData).names ?? { a: "", b: "" };
      return { ...n, data: { ...n.data, names: { a: names.b, b: names.a } } };
    }),
    revision: s.revision + 1,
  }));
  g.markDownstreamStale(fusionId);
}

export function FusionView({ node, selected, issues }: NodeViewProps<FusionConfig, FusionData>) {
  const runId = node.data.activeRunId ?? null;
  const run = useRun(runId);
  const starting = useFusionStart((s) => Boolean(s.starting[node.id]));
  const startError = useFusionStart((s) => s.errors[node.id]);
  const readOnly = useGraph((s) => s.readOnly);
  const connectivity = useConnectivity((s) => s.status);
  const { capped } = useCapped();
  const names = node.data.names ?? { a: "", b: "" };
  const style = readStyle(node.config);

  const active = starting || Boolean(run && !isTerminal(run.status));
  const now = useNow(Boolean(run && !isTerminal(run.status)), 1000);
  const since = run?.startedAt ? Date.parse(run.startedAt) : null;
  const elapsed = since ? (run?.endedAt ? Date.parse(run.endedAt) : now) - since : 0;
  const blocking = issues.filter((i) => i.severity === "block");
  const status = runStatus(run, starting) ?? (blocking.length ? { tone: "idle" as const, label: copy.status.idle } : { tone: "idle" as const, label: copy.status.ready });
  const shownError = startError ?? null;
  const countdown = useCountdown(shownError, () => void startFusion(node.id));
  // The tutorial's run is a replay (tutorial/sandbox.ts): today's cap doesn't apply to it.
  const tutorial = useWorkspaces((s) => s.currentId === TUTORIAL_WS);
  const disabledReason = blocking[0]?.message ?? (capped && !tutorial ? t.capped : null);
  // The CAP_REACHED error already says it; don't repeat it as a hint.
  const showHint = Boolean(disabledReason) && !(shownError?.code === "CAP_REACHED" && !blocking.length);

  const make = () => {
    useFusionStart.getState().clearError(node.id);
    void startFusion(node.id);
  };
  const label = shownError && presentError(shownError).retry ? t.retry : run?.status === "succeeded" ? t.makeAgain : t.make;

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
      className={[active ? "is-running" : "", shownError ? "node--error" : ""].filter(Boolean).join(" ")}
      toolbar={
        readOnly ? null : (
          <IconButton icon="replace" label={t.swap} disabled={active} onClick={() => swapSlots(node.id)} />
        )
      }
      footer={
        <>
          {active ? (
            <Button variant="primary" icon="fusion" className="nodrag fusion-node__make" busy disabled>
              {runId ? t.generating : t.starting}
            </Button>
          ) : (
            <Button
              variant="primary"
              icon="fusion"
              className="nodrag fusion-node__make"
              data-tour="make"
              disabled={Boolean(disabledReason) || countdown !== null}
              aria-describedby={showHint ? `${node.id}-hint` : undefined}
              onClick={make}
            >
              {label}
            </Button>
          )}
          {since && run && !isTerminal(run.status) ? (
            <span className="node__timer" aria-label={`${t.elapsed} ${formatElapsed(elapsed)}`}>
              {formatElapsed(elapsed)}
            </span>
          ) : null}
        </>
      }
    >
      <div className="fusion-node__parents">
        <ParentSlot nodeId={node.id} port="a" name={names.a} disabled={readOnly || active} />
        <span className="fusion-node__times" aria-hidden="true">
          ×
        </span>
        <ParentSlot nodeId={node.id} port="b" name={names.b} disabled={readOnly || active} />
      </div>
      <div className="fusion-node__mode">
        <p className="fusion-node__mode-kicker" id={`${node.id}-style`}>
          {t.style}
        </p>
        <SegmentedTabs
          label={t.style}
          value={style}
          onChange={(v) => useGraph.getState().updateNodeConfig<FusionConfig>(node.id, (c) => ({ ...c, style: v as Style }))}
          items={STYLES.map((s) => ({ value: s, label: copy.styles[s].label }))}
          disabled={active || readOnly}
        />
        <p className="fusion-node__mode-hint">{copy.styles[style].hint}</p>
      </div>
      <div className="fusion-node__messages" aria-live="polite">
        {active ? (
          <p className="node__note">
            <Icon name="info" size={14} /> {run?.status === "queued" && run.position ? copy.run.queuedLine(run.position) : copy.run.duration}
          </p>
        ) : showHint ? (
          <p id={`${node.id}-hint`} className="node__hint">
            <Icon name="info" size={14} /> {disabledReason}
          </p>
        ) : disabledReason ? null : (
          <p className="node__hint node__hint--quiet">{copy.run.duration}</p>
        )}
        {connectivity !== "online" && active ? (
          <p className="node__note node__note--warn">
            <Icon name="offline" size={14} /> {t.pausedOffline}
          </p>
        ) : null}
        {!active && shownError ? <ErrorBlock err={shownError} countdown={countdown} /> : null}
      </div>
    </NodeCard>
  );
}
