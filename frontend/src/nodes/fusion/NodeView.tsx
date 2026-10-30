import { useEffect, useRef, useState } from "react";
import type { AppError } from "../../api/errors";
import { absoluteUrl } from "../../api/client";
import { presentError } from "../../api/errorMessages";
import { NodeCard, type NodeStatus } from "../../canvas/NodeCard";
import { formatElapsed, formatSeconds, useNow } from "../../canvas/useNow";
import { useConnectivity } from "../../connectivity/store";
import { copy } from "../../copy";
import { upstreamNode } from "../../graph/queries";
import { useGraph } from "../../graph/store";
import { useRuns } from "../../runs/store";
import { TERMINAL } from "../../runs/transport";
import type { Run, Step } from "../../types/api";
import { Button } from "../../ui/Button";
import { Icon, type IconName } from "../../ui/Icon";
import type { ImageInputData } from "../image-input/types";
import { usePreview } from "../image-input/usePreview";
import { displayName } from "../result/types";
import type { NodeViewProps } from "../types";
import { FUSION_INPUTS, FUSION_OUTPUTS } from "./ports";
import type { FusionConfig, FusionData } from "./types";

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

const STEP_ICON: Record<Step["status"], IconName | null> = {
  pending: null,
  running: null,
  succeeded: "check",
  failed: "error",
  skipped: "minus",
};

function StepList({ steps, now, allDetails = false }: { steps: Step[]; now: number; allDetails?: boolean }) {
  const done = steps.filter((s) => s.status === "succeeded").length;
  // While running, only the latest finished step explains itself; failures always do.
  const lastDone = [...steps].reverse().find((s) => s.status === "succeeded")?.key;
  return (
    <div className="steps">
      {allDetails ? null : <p className="steps__count">{t.stepCount(done, steps.length)}</p>}
      <ol className="steps__list">
        {steps.map((s) => {
          const started = s.startedAt ? Date.parse(s.startedAt) : null;
          const ended = s.endedAt ? Date.parse(s.endedAt) : null;
          const ms = started ? (ended ?? now) - started : null;
          const icon = STEP_ICON[s.status];
          return (
            <li key={s.key} className={`step step--${s.status}`} aria-current={s.status === "running" ? "step" : undefined}>
              <span className="step__glyph" aria-hidden="true">
                {s.status === "running" ? <span className="pulse-dot" /> : icon ? <Icon name={icon} size={14} /> : <span className="step__hollow" />}
              </span>
              <span className="step__label">
                {s.label}
                <span className="sr-only">: {copy.steps[s.status]}</span>
              </span>
              <span className="step__time">{ms !== null && s.status !== "skipped" ? formatSeconds(ms) : ""}</span>
              {s.detail && (s.status === "failed" || (s.status === "succeeded" && (allDetails || s.key === lastDone))) ? (
                <span className="step__detail">{s.detail}</span>
              ) : null}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function totalMs(steps: Step[]): number {
  const starts = steps.map((s) => (s.startedAt ? Date.parse(s.startedAt) : NaN)).filter(Number.isFinite);
  const ends = steps.map((s) => (s.endedAt ? Date.parse(s.endedAt) : NaN)).filter(Number.isFinite);
  return starts.length && ends.length ? Math.max(...ends) - Math.min(...starts) : 0;
}

/** After success the creature leads; the step log folds away (PV1-04). */
function RunSummary({ run, now }: { run: Run; now: number }) {
  if (!run.result) return null;
  const spec = run.result.spec;
  const name = displayName(spec);
  return (
    <div className="fusion-node__summary">
      <div className="fusion-node__result">
        <img className="fusion-node__thumb" src={absoluteUrl(run.result.imageUrl)} alt={copy.nodes.result.alt(name)} draggable={false} />
        <div className="fusion-node__result-text">
          <p className="fusion-node__name">{name}</p>
          <p className="fusion-node__meta">
            {t.summary(run.steps.length, formatSeconds(totalMs(run.steps)))}
          </p>
          <p className="fusion-node__generated">
            <Icon name="leaf" size={12} /> {copy.nodes.result.generated}
          </p>
        </div>
      </div>
      <details className="steps-details">
        <summary className="steps-details__summary nodrag">{t.showSteps}</summary>
        <StepList steps={run.steps} now={now} allDetails />
      </details>
    </div>
  );
}

function InputSlot({ fusionId, port, readOnly }: { fusionId: string; port: "a" | "b"; readOnly: boolean }) {
  const nodes = useGraph((s) => s.nodes);
  const edges = useGraph((s) => s.edges);
  const up = upstreamNode({ nodes, edges }, fusionId, port);
  const upData = up?.data as ImageInputData | undefined;
  const preview = usePreview(upData ?? {});
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
        ...(sourceId ? [{ id: `e-${port}-${fusionId}-${Date.now().toString(36)}`, source: sourceId, sourcePort: "out", target: fusionId, targetPort: port }] : []),
      ],
      revision: s.revision + 1,
    }));
    if (existing?.source !== sourceId) g.markDownstreamStale(fusionId);
  };

  return (
    <div className={`input-slot${up ? " is-filled" : ""}`}>
      <span className="input-slot__letter" aria-hidden="true">
        {slot}
      </span>
      <span className="input-slot__thumb" aria-hidden="true">
        {preview ? <img src={preview} alt="" /> : <Icon name="image" size={16} />}
      </span>
      <label className="sr-only" htmlFor={selectId}>
        {t.connectVia(slot)}
      </label>
      <select
        id={selectId}
        className="input-slot__select nodrag"
        value={up?.id ?? ""}
        disabled={readOnly}
        onChange={(e) => connect(e.target.value)}
      >
        <option value="">{up ? t.empty : t.chooseImage}</option>
        {images.map((img, i) => (
          <option key={img.id} value={img.id}>
            {`${i + 1}. ${(img.data as ImageInputData).fileName || copy.nodes.imageInput.untitled}`}
          </option>
        ))}
      </select>
    </div>
  );
}

/** Auto-retry countdown for RATE_LIMITED (uses retryAfterMs). */
function useCountdown(err: AppError | null | undefined, onDone: () => void): number | null {
  const [left, setLeft] = useState<number | null>(null);
  const fired = useRef<AppError | null>(null);
  const done = useRef(onDone);
  done.current = onDone;
  useEffect(() => {
    if (!err || err.code !== "RATE_LIMITED" || fired.current === err) {
      setLeft(null);
      return;
    }
    const until = Date.now() + Math.max(1000, err.retryAfterMs ?? 4000);
    const tick = () => {
      const ms = until - Date.now();
      if (ms <= 0) {
        fired.current = err;
        setLeft(null);
        done.current();
      } else setLeft(Math.ceil(ms / 1000));
    };
    tick();
    const id = setInterval(tick, 250);
    return () => clearInterval(id);
  }, [err]);
  return left;
}

/** The footer's primary button is the retry action; this block explains what happened. */
function ErrorBlock({ err, countdown }: { err: AppError; countdown: number | null }) {
  const p = presentError(err);
  return (
    <div className="node__error" role="alert">
      <p className="node__error-title">
        <Icon name="error" size={14} /> {p.title}
      </p>
      {p.fix ? <p className="node__error-fix">{p.fix}</p> : null}
      {p.errorId ? <p className="node__error-id">{copy.errors.reportId(p.errorId)}</p> : null}
      {countdown !== null ? (
        <p className="node__error-fix" aria-live="polite">
          {t.retryIn(countdown)}
        </p>
      ) : null}
    </div>
  );
}

export function FusionView({ node, selected, issues, catalog }: NodeViewProps<FusionConfig, FusionData>) {
  const runId = node.data.activeRunId ?? null;
  const run = useRuns((s) => (runId ? s.runs[runId] : undefined));
  const starting = useRuns((s) => Boolean(s.starting[node.id]));
  const startError = useRuns((s) => s.startErrors[node.id]);
  const start = useRuns((s) => s.start);
  const cancel = useRuns((s) => s.cancel);
  const readOnly = useGraph((s) => s.readOnly);
  const connectivity = useConnectivity((s) => s.status);
  const [cancelling, setCancelling] = useState(false);

  const active = starting || (run !== undefined && !TERMINAL.has(run.status));
  const now = useNow(active, 500);
  const elapsed = run ? now - Date.parse(run.createdAt) : 0;
  const blocking = issues.filter((i) => i.severity === "block");
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
      catalog={catalog}
      title={t.title}
      icon="fusion"
      status={status}
      inputs={FUSION_INPUTS}
      outputs={FUSION_OUTPUTS}
      selected={selected}
      className={[active ? "is-running" : "", shownError ? "node--error" : "", stale ? "is-stale" : ""].filter(Boolean).join(" ")}
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
      <div className="fusion-node__inputs">
        <InputSlot fusionId={node.id} port="a" readOnly={readOnly || active} />
        <InputSlot fusionId={node.id} port="b" readOnly={readOnly || active} />
      </div>
      {run ? run.status === "succeeded" && !active ? <RunSummary run={run} now={now} /> : <StepList steps={run.steps} now={now} /> : null}
      <div className="fusion-node__messages" aria-live="polite">
        {!active && blocking[0] ? (
          <p id={`${node.id}-hint`} className="node__hint">
            <Icon name="info" size={14} /> {blocking[0].message}
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
    </NodeCard>
  );
}
