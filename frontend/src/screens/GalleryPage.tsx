import { useEffect, useState } from "react";
import { hrefFor, linkHandler, navigate } from "../app/route";
import { ErrorBlock } from "../canvas/RunParts";
import { copy } from "../copy";
import { useCapped, useGallery, useLimits } from "../evo/data";
import { evo } from "../evo/index";
import type { GalleryItem } from "../evo/types";
import { utcClock } from "../trace/time";
import { Button } from "../ui/Button";
import { Icon } from "../ui/Icon";
import { Pill } from "../ui/Pill";

const t = copy.gallery;

function Card({ item }: { item: GalleryItem }) {
  const [broken, setBroken] = useState(false);
  const route = { view: "creature", creatureId: item.creatureId } as const;
  return (
    <li className="gcard">
      <a className="gcard__link" href={hrefFor(route)} onClick={linkHandler(route)}>
        <span className="gcard__frame">
          {broken ? (
            <span className="gcard__broken">
              <Icon name="image" size={24} />
            </span>
          ) : (
            <img className="gcard__img" src={evo().imageUrl(item.imageUrl)} alt={copy.labels.alt(item.title)} loading="lazy" onError={() => setBroken(true)} />
          )}
          <span className="gcard__label">
            <Pill tone="brand">
              <Icon name="leaf" size={12} /> {copy.labels.generated}
            </Pill>
          </span>
        </span>
        <span className="gcard__body">
          <span className="gcard__kicker">{copy.modes[item.mode]?.label ?? item.mode}</span>
          <span className="gcard__title">{item.title}</span>
          <span className="gcard__parents">
            {item.sire.scientificName ? <span className="binomial">{item.sire.scientificName}</span> : item.sire.commonName}
            {" × "}
            {item.dam.scientificName ? <span className="binomial">{item.dam.scientificName}</span> : item.dam.commonName}
          </span>
        </span>
      </a>
    </li>
  );
}

/** Today's live runs, in words. Shown before anyone uploads anything. */
export function LimitsLine() {
  const limits = useLimits((s) => s.data);
  const { capped, resetsAt } = useCapped();
  if (capped) {
    const at = utcClock(resetsAt);
    return (
      <div className="cap-card" role="status">
        <Icon name="alert" size={16} />
        <div>
          <p className="cap-card__title">{t.cappedTitle}</p>
          <p className="cap-card__body">{t.cappedBody(at)}</p>
        </div>
      </div>
    );
  }
  if (!limits) return <p className="limits-line">{copy.trace.duration}</p>;
  const left = Math.max(0, limits.dailyTotal.limit - limits.dailyTotal.used);
  const mine = Math.max(0, limits.visitor.limit - limits.visitor.used);
  return <p className="limits-line">{t.limits(left, limits.dailyTotal.limit, mine)}</p>;
}

export function GalleryPage() {
  const { status, data, error, nextCursor, loadingMore, load, more } = useGallery();
  const { capped } = useCapped();

  useEffect(() => {
    if (status === "idle") void load();
  }, [status, load]);

  return (
    <div className="page page--gallery">
      <section className="hero" aria-labelledby="hero-title">
        <div className="hero__text">
          <p className="hero__kicker">{t.kicker}</p>
          <h1 id="hero-title" className="hero__title">
            {t.title}
          </h1>
          <p className="hero__lead">{t.lead}</p>
        </div>
        <div className="hero__action">
          <Button variant="primary" className="btn--lg hero__make" onClick={() => navigate({ view: "studio" })}>
            Open creative studio
          </Button>
          <Button variant="primary" icon="fusion" className="btn--lg hero__make" disabled={capped} aria-describedby="limits-line" onClick={() => navigate({ view: "lab", runId: null })}>
            {t.make}
          </Button>
          <div id="limits-line">
            <LimitsLine />
          </div>
        </div>
      </section>

      <section className="gallery" aria-labelledby="gallery-title" aria-busy={status === "loading"}>
        <div className="gallery__head">
          <h2 id="gallery-title" className="gallery__title">
            {t.showcase}
          </h2>
          <p className="gallery__note">{t.note}</p>
        </div>
        {status === "error" && error ? (
          <div className="gallery__error">
            <ErrorBlock err={error} />
            <Button icon="refresh" onClick={() => void load()}>
              {t.retry}
            </Button>
          </div>
        ) : status !== "ready" ? (
          <ul className="gallery-grid" aria-label={t.loading}>
            {Array.from({ length: 6 }, (_, i) => (
              <li key={i} className="gcard gcard--skeleton" aria-hidden="true">
                <span className="gcard__frame">
                  <span className="skeleton skeleton--fill" />
                </span>
                <span className="gcard__body">
                  <span className="skeleton skeleton--line" />
                  <span className="skeleton skeleton--line skeleton--short" />
                </span>
              </li>
            ))}
          </ul>
        ) : data && data.length ? (
          <>
            <ul className="gallery-grid">
              {data.map((item) => (
                <Card key={item.creatureId} item={item} />
              ))}
            </ul>
            {nextCursor ? (
              <div className="gallery__more">
                <Button busy={loadingMore} onClick={() => void more()}>
                  {t.more}
                </Button>
              </div>
            ) : null}
          </>
        ) : (
          <p className="gallery__empty">{t.empty}</p>
        )}
      </section>
    </div>
  );
}
