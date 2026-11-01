import { useEffect, useRef } from "react";
import { navigate } from "../app/route";
import { ErrorBlock } from "../canvas/RunParts";
import { formatElapsed, useNow } from "../canvas/useNow";
import { copy } from "../copy";
import { useCreature } from "../evo/data";
import { evo } from "../evo/index";
import { isTerminal, useEvoRuns, useRun, useRunRecord, type DerivedRun } from "../evo/runs";
import { useGraph } from "../graph/store";
import { startFusion } from "../nodes/fusion/start";
import type { FusionData } from "../nodes/fusion/types";
import { Button, IconButton } from "../ui/Button";
import { Icon } from "../ui/Icon";
import { LiveIndicator } from "../ui/LiveIndicator";
import { Pill } from "../ui/Pill";
import { ChoiceCard } from "./ChoiceCard";
import { TraceLog } from "./TraceLog";

const t = copy.trace;

function title(run: DerivedRun | null): string {
  return run?.sire && run.dam ? `${run.sire.commonName} × ${run.dam.commonName}` : t.untitled;
}

/** Queued / running / waiting for you: what is happening now, and how long it takes. */
function NowCard({ run, reconnecting }: { run: DerivedRun; reconnecting: boolean }) {
  const now = useNow(!isTerminal(run.status), 1000);
  const elapsed = run.startedAt ? now - Date.parse(run.startedAt) : 0;
  if (run.status === "loading") {
    return (
      <section className="now-card" aria-busy="true">
        <LiveIndicator tone="running" label={copy.status.connecting} />
        <p className="now-card__body">{t.connecting}</p>
      </section>
    );
  }
  if (run.status === "queued") {
    return (
      <section className="now-card now-card--queued">
        <div className="now-card__head">
          <LiveIndicator tone="warn" label={copy.status.queued} />
        </div>
        <p className="now-card__big">{run.position ? t.position(run.position) : t.inQueue}</p>
        <p className="now-card__body">{run.ahead !== null ? t.ahead(run.ahead) : t.queuedWait}</p>
        <p className="now-card__body">{t.duration}</p>
      </section>
    );
  }
  const rendersCap = run.caps?.renders ?? null;
  return (
    <section className="now-card">
      <div className="now-card__head">
        <LiveIndicator tone={run.status === "needs_choice" ? "warn" : "running"} label={run.status === "needs_choice" ? copy.status.needsChoice : copy.status.running} />
        {run.startedAt ? (
          <span className="now-card__timer" aria-label={`${copy.nodes.fusion.elapsed} ${formatElapsed(elapsed)}`}>
            {formatElapsed(elapsed)}
          </span>
        ) : null}
      </div>
      <p className="now-card__body">{t.duration}</p>
      <dl className="now-card__stats">
        <div>
          <dt>{t.statSteps}</dt>
          <dd>{run.caps ? `${run.toolCalls} / ${run.caps.toolCalls}` : run.toolCalls}</dd>
        </div>
        <div>
          <dt>{t.statRenders}</dt>
          <dd>{rendersCap ? `${run.rendersUsed} / ${rendersCap}` : run.rendersUsed}</dd>
        </div>
      </dl>
      {run.status !== "needs_choice" ? <span className="progress-indeterminate" aria-hidden="true" /> : null}
      {run.capNotice ? (
        <p className="now-card__cap">
          <Icon name="alert" size={14} /> {t.capNotice(run.capNotice.scope, run.capNotice.limit)}
        </p>
      ) : null}
      {reconnecting ? (
        <p className="now-card__note">
          <Icon name="offline" size={14} /> {t.reconnecting}
        </p>
      ) : null}
      <p className="now-card__note">{t.leaveOk}</p>
    </section>
  );
}

/** Finished: the creature leads, with what the card says about it, and the way to the full card. */
function ResultSummary({ run }: { run: DerivedRun }) {
  const fin = run.finalize!;
  const c = useCreature(fin.creatureId);
  const creature = c.data;
  return (
    <section className="result-sum" aria-labelledby="result-sum-title">
      <figure className="result-sum__figure">
        <img className="result-sum__img" src={evo().imageUrl(fin.imageUrl)} alt={copy.labels.alt(creature?.title ?? title(run))} />
        <figcaption className="result-sum__cap">
          <Pill tone="indigo">
            <Icon name="leaf" size={12} /> {creature?.generatedLabel ?? copy.labels.generated}
          </Pill>
          {creature?.realHybrid ? (
            <Pill tone="info">
              <span className="pill__diamond" aria-hidden="true" /> {copy.labels.realHybrid}
            </Pill>
          ) : null}
        </figcaption>
      </figure>
      <div className="result-sum__text">
        <p className="result-sum__kicker">{t.finished}</p>
        <h3 id="result-sum-title" className="result-sum__title">
          {creature?.title ?? title(run)}
        </h3>
        {creature ? (
          <>
            <p className="result-sum__line">
              <strong>{copy.creature.hostIs(creature.host.commonName)}</strong> {copy.creature.chosenBy(creature.host.chosenBy)}
            </p>
            <p className="result-sum__line">{creature.canItLive.summary}</p>
          </>
        ) : c.status === "error" ? (
          <p className="result-sum__line">{t.cardUnavailable}</p>
        ) : (
          <p className="result-sum__line">{t.loadingCard}</p>
        )}
        <p className="result-sum__line result-sum__line--muted">
          {fin.remainingFailures.length ? t.remaining(fin.remainingFailures.length) : t.noRemaining}
          {fin.hiddenChecks > 0 ? ` ${copy.labels.hiddenChecks(fin.hiddenChecks)}` : ""}
        </p>
        <div className="result-sum__actions">
          <Button variant="primary" icon="card" onClick={() => navigate({ view: "creature", creatureId: fin.creatureId })}>
            {t.openCard}
          </Button>
        </div>
      </div>
    </section>
  );
}

function FailedCard({ run }: { run: DerivedRun }) {
  const nodeId = useGraph((s) => s.nodes.find((n) => n.type === "fusion" && ((n.data as FusionData).runIds ?? []).includes(run.runId))?.id);
  const err = run.error ?? { code: run.status === "interrupted" ? "RUN_INTERRUPTED" : "UNKNOWN", message: "", retryable: true };
  return (
    <section className="now-card now-card--error">
      <LiveIndicator tone="error" label={run.status === "interrupted" ? copy.status.interrupted : copy.status.failed} />
      <ErrorBlock err={{ ...err, code: err.code as never }} className="now-card__error" />
      <div className="now-card__actions">
        {nodeId && err.retryable ? (
          <Button variant="primary" icon="refresh" onClick={() => void startFusion(nodeId)}>
            {t.tryAgain}
          </Button>
        ) : (
          <Button variant="primary" icon="fusion" onClick={() => navigate({ view: "lab", runId: null })}>
            {copy.gallery.make}
          </Button>
        )}
      </div>
    </section>
  );
}

/** The live trace of one agent run, docked beside the canvas (full screen on narrow viewports). */
export function TracePanel({ runId }: { runId: string }) {
  const rec = useRunRecord(runId);
  const run = useRun(runId);
  const attach = useEvoRuns((s) => s.attach);
  const closeRef = useRef<HTMLButtonElement>(null);
  const logEnd = useRef<HTMLDivElement>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);

  useEffect(() => attach(runId), [runId, attach]);

  // Follow new steps while the reader is at the bottom; never yank them away from what they are reading.
  const count = run?.items.length ?? 0;
  useEffect(() => {
    if (!run || isTerminal(run.status) || !pinned.current) return;
    logEnd.current?.scrollIntoView?.({ block: "end" });
  }, [count, run]);

  const onScroll = () => {
    const el = scroller.current;
    if (el) pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };

  const close = () => navigate({ view: "lab", runId: null });
  const done = run ? isTerminal(run.status) : false;

  // When the run ends, the creature (or the error) at the top leads: bring it into view once.
  useEffect(() => {
    if (done && scroller.current) scroller.current.scrollTop = 0;
  }, [done]);

  return (
    <aside className="trace" aria-labelledby="trace-title">
      <header className="trace__header">
        <div className="trace__heading">
          <p className="trace__kicker">{done ? t.kickerDone : t.kicker}</p>
          <h2 id="trace-title" className="trace__title">
            {title(run)}
          </h2>
          <p className="trace__meta">
            {run?.mode ? <Pill tone="neutral">{copy.modes[run.mode].label}</Pill> : null}
            <span className="trace__runid">{runId}</span>
          </p>
        </div>
        <IconButton ref={closeRef} icon="close" label={t.hide} onClick={close} />
      </header>
      {run && !done && !rec?.loadError ? (
        // What is happening now (and a question for you) stays in view while the steps scroll below.
        <div className="trace__now" tabIndex={0} role="region" aria-label={t.nowLabel}>
          <NowCard run={run} reconnecting={rec?.stream === "reconnecting"} />
          {run.pendingChoice ? <ChoiceCard runId={runId} choice={run.pendingChoice} /> : null}
        </div>
      ) : null}
      <div className="trace__scroll" ref={scroller} onScroll={onScroll} tabIndex={0} role="region" aria-label={t.scrollLabel}>
        {rec?.loadError && !run?.items.length ? (
          <section className="now-card now-card--error">
            <ErrorBlock err={rec.loadError.code === "NOT_FOUND" ? { ...rec.loadError, code: "RUN_NOT_FOUND" } : rec.loadError} />
            <div className="now-card__actions">
              <Button variant="primary" icon="fusion" onClick={() => navigate({ view: "lab", runId: null })}>
                {copy.gallery.make}
              </Button>
              <Button variant="ghost" onClick={() => navigate({ view: "gallery" })}>
                {copy.nav.gallery}
              </Button>
            </div>
          </section>
        ) : run ? (
          <>
            {run.status === "succeeded" && run.finalize ? <ResultSummary run={run} /> : null}
            {run.status === "failed" || run.status === "interrupted" ? <FailedCard run={run} /> : null}
            {run.items.length ? <h3 className="trace__log-title">{done ? t.howMade(run.toolCalls) : t.steps}</h3> : null}
            <TraceLog run={run} label={t.logLabel} />
            <div ref={logEnd} />
          </>
        ) : null}
      </div>
    </aside>
  );
}
