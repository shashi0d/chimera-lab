import { copy } from "../copy";
import { evo } from "../evo/index";
import type { DerivedRun, TraceItem, TraceStep } from "../evo/runs";
import type { InspectEvent, RenderEvent } from "../evo/types";
import { Icon } from "../ui/Icon";
import { Pill } from "../ui/Pill";
import { offset } from "./time";

const t = copy.trace;

/** A generated image in the trace: always captioned "Generated fusion", never presented as a real animal. */
export function TraceImage({ render, verdict }: { render: RenderEvent; verdict?: InspectEvent }) {
  return (
    <figure className="trace-img">
      <img className="trace-img__img" src={evo().imageUrl(render.url)} alt={t.imageAlt(render.imageId)} loading="lazy" />
      <figcaption className="trace-img__cap">
        <span className="trace-img__label">{copy.labels.generated}</span>
        <span className="trace-img__id">
          {render.imageId} · {t.kind(render.kind)}
        </span>
        {verdict ? <Verdict v={verdict.verdict} /> : null}
      </figcaption>
    </figure>
  );
}

export function Verdict({ v }: { v: string }) {
  const pass = v === "pass";
  return (
    <span className={`verdict verdict--${pass ? "pass" : "fail"}`}>
      <Icon name={pass ? "check" : "error"} size={12} /> {pass ? t.pass : t.fail}
    </span>
  );
}

function Inspection({ e }: { e: InspectEvent }) {
  return (
    <div className="trace-inspect">
      <p className="trace-inspect__head">
        <Verdict v={e.verdict} />
        <span>{e.failures.length ? t.failedChecks(e.failures.length) : t.allChecksPass}</span>
      </p>
      {e.failures.length ? (
        <ul className="trace-inspect__list">
          {e.failures.map((f) => (
            <li key={f.key} className="trace-inspect__item">
              <span className={`kind-tag kind-tag--${f.kind === "structural" ? "structural" : "covering"}`}>{t.failureKind(f.kind)}</span> {f.text}
            </li>
          ))}
        </ul>
      ) : null}
      {e.hiddenChecks > 0 ? <p className="trace-inspect__hidden">{copy.labels.hiddenChecks(e.hiddenChecks)}</p> : null}
    </div>
  );
}

function StepRow({ s, start, verdicts }: { s: TraceStep; start: string | null; verdicts: DerivedRun["verdicts"] }) {
  const step = s.step;
  const tool = step?.tool ?? (s.renders.length ? "render" : "inspect");
  return (
    <li className={`trace-row trace-row--step${step && !step.ok ? " is-failed" : ""}`}>
      <span className="trace-row__n" aria-hidden="true">
        {Math.floor(s.n)}
      </span>
      <div className="trace-row__body">
        <p className="trace-row__title">
          <span className="sr-only">{t.stepN(Math.floor(s.n))}: </span>
          {t.tool(tool)}
          <span className="trace-row__time">{offset(s.at, start)}</span>
        </p>
        {step?.reason ? <p className="trace-row__reason">{step.reason}</p> : null}
        {step?.summary ? <p className="trace-row__summary">{step.summary}</p> : null}
        {step && !step.ok ? (
          <p className="trace-row__error">
            <Icon name="alert" size={14} /> {t.stepRefused(step.error)}
          </p>
        ) : null}
        {s.renders.length ? (
          <div className="trace-row__images">
            {s.renders.map((r) => (
              <TraceImage key={r.imageId} render={r} verdict={verdicts[r.imageId]} />
            ))}
          </div>
        ) : null}
        {s.inspect ? <Inspection e={s.inspect} /> : null}
        {step?.cards.length ? <p className="trace-row__cards">{t.rules(step.cards.join(", "))}</p> : null}
      </div>
    </li>
  );
}

function Row({ item, run }: { item: TraceItem; run: DerivedRun }) {
  const start = run.startedAt;
  switch (item.kind) {
    case "step":
      return <StepRow s={item.data} start={start} verdicts={run.verdicts} />;
    case "queued":
      return (
        <li className="trace-row trace-row--note">
          <Icon name="info" size={16} />
          <p className="trace-row__note">{t.queuedRow(item.position, item.ahead)}</p>
        </li>
      );
    case "started":
      return (
        <li className="trace-row trace-row--note">
          <Icon name="fusion" size={16} />
          <p className="trace-row__note">
            {t.startedRow(item.event.sire.commonName, item.event.dam.commonName, copy.modes[item.event.mode]?.label ?? item.event.mode)}{" "}
            <span className="trace-row__meta">{t.caps(item.event.caps.renders, item.event.caps.toolCalls, Math.round(item.event.caps.seconds / 60))}</span>
          </p>
        </li>
      );
    case "choice":
      return (
        <li className="trace-row trace-row--note trace-row--choice">
          <Icon name="help" size={16} />
          <p className="trace-row__note">
            {t.askedRow(item.event.question)}{" "}
            <strong>{item.by === null ? t.waitingAnswer : item.by === "timeout" ? t.timedOut : t.youChose(item.answer ?? "")}</strong>
          </p>
        </li>
      );
    case "cap":
      return (
        <li className="trace-row trace-row--note trace-row--warn">
          <Icon name="alert" size={16} />
          <p className="trace-row__note">{t.capRow(item.event.scope, item.event.limit)}</p>
        </li>
      );
    case "finalize":
      return (
        <li className="trace-row trace-row--note trace-row--ok">
          <Icon name="check" size={16} />
          <p className="trace-row__note">
            {t.finalRow(item.event.imageId)} <span className="trace-row__meta">{item.event.stop}</span>
          </p>
        </li>
      );
    case "error":
      return (
        <li className="trace-row trace-row--note trace-row--error">
          <Icon name="error" size={16} />
          <p className="trace-row__note">{t.errorRow}</p>
        </li>
      );
  }
}

/** Every step as it streams, with the agent's reason in its own words. */
export function TraceLog({ run, label }: { run: DerivedRun; label: string }) {
  if (!run.items.length) return null;
  return (
    // role="log" sits on a wrapper so the <ol> keeps its list semantics.
    <div role="log" aria-live="polite" aria-relevant="additions" aria-label={label}>
      <ol className="trace-log">
        {run.items.map((item) => (
          <Row key={item.key} item={item} run={run} />
        ))}
      </ol>
    </div>
  );
}

export function StepCountPill({ run }: { run: DerivedRun }) {
  return <Pill tone="neutral">{t.stepsCount(run.toolCalls)}</Pill>;
}
