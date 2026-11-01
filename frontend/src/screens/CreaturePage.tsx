import { useState } from "react";
import { hrefFor, linkHandler, navigate } from "../app/route";
import { ErrorBlock } from "../canvas/RunParts";
import { copy } from "../copy";
import { useCreature } from "../evo/data";
import { evo } from "../evo/index";
import type { AnatomyPart, Creature, Pick as ImagePick } from "../evo/types";
import { Verdict } from "../trace/TraceLog";
import { Button } from "../ui/Button";
import { Icon } from "../ui/Icon";
import { Pill } from "../ui/Pill";
import { StatCard } from "../ui/StatCard";

const t = copy.creature;
const ROLES = ["host", "donor", "blend"] as const;

/** Swatch in the API's own overlay colour (anatomyMap.colors), so the legend always matches the overlay image. */
function Swatch({ color }: { color: string | null }) {
  return (
    <svg className="swatch" viewBox="0 0 14 14" aria-hidden="true" focusable="false">
      {color ? <rect x="1" y="1" width="12" height="12" rx="3" fill={color} /> : <rect x="1.5" y="1.5" width="11" height="11" rx="3" className="swatch__empty" />}
    </svg>
  );
}

function Legend({ map, c }: { map: NonNullable<Creature["anatomyMap"]>; c: Creature }) {
  const byRole = ROLES.map((role) => ({ role, parts: map.parts.filter((p) => p.parentRole === role && p.status === "found") })).filter((g) => g.parts.length);
  const missing = map.parts.filter((p) => p.status !== "found");
  const parentFor = (parts: AnatomyPart[]) => [...new Set(parts.map((p) => p.parent))].join(", ");
  return (
    <div className="legend" aria-label={t.legendLabel}>
      <ul className="legend__list">
        {byRole.map((g) => (
          <li key={g.role} className="legend__row">
            <Swatch color={map.colors[g.role]} />
            <span className="legend__role">{t.role(g.role)}</span>
            <span className="legend__parent">{parentFor(g.parts)}</span>
            <span className="legend__parts">{g.parts.map((p) => p.part).join(", ")}</span>
          </li>
        ))}
      </ul>
      {missing.length ? (
        <p className="legend__missing">
          <Swatch color={null} /> {t.notLocated(missing.map((p) => p.part).join(", "))}
        </p>
      ) : null}
      <p className="legend__note">{t.legendNote(c.host.commonName)}</p>
    </div>
  );
}

function Hero({ c }: { c: Creature }) {
  const [overlay, setOverlay] = useState(false);
  const map = c.anatomyMap;
  const src = overlay && map ? map.overlayUrl : c.imageUrl;
  return (
    <div className="creature__media">
      <figure className="creature__figure">
        <div className={`creature__frame${overlay ? " is-overlay" : ""}`}>
          <img className="creature__img" src={evo().imageUrl(src)} alt={overlay ? t.overlayAlt(c.title) : copy.labels.alt(c.title)} />
        </div>
        <figcaption className="creature__cap">
          <Pill tone="indigo">
            <Icon name="leaf" size={12} /> {c.generatedLabel || copy.labels.generated}
          </Pill>
          <span className="creature__cap-text">{overlay ? t.overlayCaption : t.notReal}</span>
        </figcaption>
      </figure>
      {map ? (
        <div className="creature__overlay">
          <button type="button" className={`switch${overlay ? " is-on" : ""}`} aria-pressed={overlay} onClick={() => setOverlay((v) => !v)}>
            <span className="switch__track" aria-hidden="true">
              <span className="switch__thumb" />
            </span>
            <span className="switch__label">{t.overlay}</span>
          </button>
          {overlay ? <Legend map={map} c={c} /> : <p className="creature__overlay-hint">{t.overlayHint}</p>}
        </div>
      ) : null}
    </div>
  );
}

function PickFigure({ pick, who, first }: { pick: ImagePick; who: "agent" | "code"; first: boolean }) {
  return (
    <figure className={`pick${first ? " pick--first" : ""}`}>
      <img className="pick__img" src={evo().imageUrl(pick.imageUrl)} alt={t.pickAlt(who, pick.imageId)} />
      <figcaption className="pick__cap">
        <span className="pick__who">{t.pickBy(who)}</span>
        <span className="pick__label">{copy.labels.generated}</span>
        <span className="pick__rank">{t.rank(pick.imageId, pick.rank, pick.of)}</span>
        <span className="pick__counts">{t.counts(pick.structural, pick.failures)}</span>
        <span className="pick__reason">{pick.reason}</span>
      </figcaption>
    </figure>
  );
}

function CreatureBody({ c }: { c: Creature }) {
  const live = c.canItLive;
  const structural = c.remainingFailures.filter((f) => f.kind === "structural");
  const covering = c.remainingFailures.filter((f) => f.kind !== "structural");
  return (
    <article className="creature" aria-labelledby="creature-title">
      <Hero c={c} />
      <div className="creature__info">
        <p className="creature__kicker">
          {copy.modes[c.mode]?.label ?? c.mode}
          {c.showcase ? ` · ${t.showcase}` : ""}
        </p>
        <h1 id="creature-title" className="creature__title">
          {c.title}
        </h1>
        <p className="creature__parents">
          {[c.sire, c.dam].map((p, i) => (
            <span key={i}>
              {i ? " × " : ""}
              {p.commonName}
              {p.scientificName ? (
                <>
                  {" "}
                  (<span className="binomial">{p.scientificName}</span>)
                </>
              ) : null}
            </span>
          ))}
        </p>
        {c.realHybrid ? (
          <div className="hybrid-note">
            <Pill tone="info">
              <span className="pill__diamond" aria-hidden="true" /> {copy.labels.realHybrid}
            </Pill>
            <p>{t.realHybridNote}</p>
          </div>
        ) : null}

        <section className="cblock" aria-labelledby="host-h">
          <h2 id="host-h" className="cblock__title">
            {t.hostTitle}
          </h2>
          <p className="cblock__lead">
            <strong>{t.hostIs(c.host.commonName)}</strong> {t.chosenBy(c.host.chosenBy)}
            {c.host.tie ? ` ${t.tie}` : ""}
          </p>
          <blockquote className="cblock__quote">{c.host.reason}</blockquote>
        </section>

        <section className="cblock" aria-labelledby="live-h">
          <h2 id="live-h" className="cblock__title">
            {t.liveTitle}
          </h2>
          <p className="cblock__lead">{live.summary}</p>
          <ul className="fn-list">
            {live.functions.map((f) => (
              <li key={f.function} className="fn-list__row">
                <Verdict v={f.result} />
                <span className="fn-list__name">{f.function}</span>
                <span className="fn-list__detail">{f.detail}</span>
              </li>
            ))}
          </ul>
          {live.licenses.length ? (
            <div className="cblock__sub">
              <h3 className="cblock__subtitle">{t.licenses}</h3>
              <ul className="plain-list">
                {live.licenses.map((l) => (
                  <li key={l.rule}>
                    {l.rule}: {l.compensation}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>

        <section className="cblock" aria-labelledby="checks-h">
          <h2 id="checks-h" className="cblock__title">
            {t.checksTitle}
          </h2>
          {c.remainingFailures.length ? (
            <ul className="check-list">
              {[...structural, ...covering].map((f) => (
                <li key={f.key} className="check-list__row">
                  <span className={`kind-tag kind-tag--${f.kind === "structural" ? "structural" : "covering"}`}>{copy.trace.failureKind(f.kind)}</span>
                  <span>{f.text}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="cblock__lead">
              <Icon name="check" size={14} /> {t.noFailures}
            </p>
          )}
          {c.hiddenChecks > 0 ? (
            <p className="hidden-checks">
              <Icon name="info" size={14} /> <strong>{copy.labels.hiddenChecks(c.hiddenChecks)}</strong> {t.hiddenWhy}
            </p>
          ) : null}
        </section>

        {!c.finalChoice.agree ? (
          <section className="cblock cblock--picks" aria-labelledby="picks-h">
            <h2 id="picks-h" className="cblock__title">
              {t.picksTitle}
            </h2>
            <p className="cblock__lead">{t.picksLead}</p>
            <div className="picks">
              <PickFigure pick={c.finalChoice.agentPick} who="agent" first />
              <PickFigure pick={c.finalChoice.codePick} who="code" first={false} />
            </div>
          </section>
        ) : null}

        {c.images.length > 1 ? (
          <section className="cblock" aria-labelledby="images-h">
            <h2 id="images-h" className="cblock__title">
              {t.imagesTitle(c.images.length)}
            </h2>
            <ul className="img-strip">
              {c.images.map((im) => (
                <li key={im.imageId} className="img-strip__item">
                  <img className="img-strip__img" src={evo().imageUrl(im.url)} alt={copy.trace.imageAlt(im.imageId)} loading="lazy" />
                  <span className="img-strip__cap">
                    {im.imageId} · {copy.trace.kind(im.kind)}
                  </span>
                  {im.verdict ? <Verdict v={im.verdict} /> : null}
                </li>
              ))}
            </ul>
            <p className="img-strip__note">{t.allGenerated}</p>
          </section>
        ) : null}

        <div className="stats creature__stats">
          <StatCard kicker={t.statRenders} value={c.stats.renders} meta={t.statEdits(c.stats.edits)} />
          <StatCard kicker={t.statTools} value={c.stats.toolCalls} meta={t.statToolsMeta} />
          <StatCard kicker={t.statTime} value={t.minutes(c.stats.seconds)} meta={t.statTimeMeta} />
        </div>

        <div className="creature__actions">
          {c.runId ? (
            <a className="btn btn--secondary" href={hrefFor({ view: "lab", runId: c.runId })} onClick={linkHandler({ view: "lab", runId: c.runId })}>
              <Icon name="info" size={16} />
              <span className="btn__label">{t.seeTrace}</span>
            </a>
          ) : null}
          <Button variant="primary" icon="fusion" onClick={() => navigate({ view: "lab", runId: null })}>
            {copy.gallery.make}
          </Button>
        </div>
      </div>
    </article>
  );
}

export function CreaturePage({ creatureId }: { creatureId: string }) {
  const { status, data, error, reload } = useCreature(creatureId);
  return (
    <div className="page page--creature">
      <nav className="crumbs" aria-label={t.crumbs}>
        <a className="crumbs__link" href={hrefFor({ view: "gallery" })} onClick={linkHandler({ view: "gallery" })}>
          <Icon name="left" size={16} /> {copy.nav.gallery}
        </a>
      </nav>
      {data ? (
        <CreatureBody c={data} />
      ) : status === "error" && error ? (
        <div className="page-error">
          <h1 className="page-error__title">{error.code === "NOT_FOUND" ? t.notFound : t.loadFailed}</h1>
          <ErrorBlock err={error} />
          <div className="page-error__actions">
            {error.retryable ? (
              <Button icon="refresh" onClick={reload}>
                {t.retry}
              </Button>
            ) : null}
            <Button variant="primary" onClick={() => navigate({ view: "gallery" })}>
              {copy.nav.gallery}
            </Button>
          </div>
        </div>
      ) : (
        <div className="creature creature--loading" aria-busy="true" aria-label={t.loading}>
          <div className="creature__media">
            <div className="creature__frame">
              <span className="skeleton skeleton--fill" />
            </div>
          </div>
          <div className="creature__info">
            <span className="skeleton skeleton--line" />
            <span className="skeleton skeleton--line skeleton--short" />
          </div>
        </div>
      )}
    </div>
  );
}
