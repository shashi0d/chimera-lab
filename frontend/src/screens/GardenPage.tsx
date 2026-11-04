import { useCallback, useEffect, useState } from "react";
import { toAppError } from "../api/errors";
import { presentError } from "../api/errorMessages";
import { hrefFor, linkHandler } from "../app/route";
import { copy } from "../copy";
import { CardTile } from "../lab/CardTile";
import { labApi, type LabVersion } from "../lab/api";

const POLL_MS = 15000;

/** The Garden: every creature its maker shared, by anyone, as field-guide cards (read-only). */
export function GardenPage() {
  const [items, setItems] = useState<LabVersion[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const t = copy.garden;

  const load = useCallback(async () => {
    try {
      setItems(await labApi.garden());
      setError(null);
    } catch (e) {
      setError(presentError(toAppError(e)).title);
    }
  }, []);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(), POLL_MS);
    return () => window.clearInterval(id);
  }, [load]);

  return (
    <section className="chimeras garden" aria-labelledby="garden-title">
      <header className="chimeras__head">
        <h1 id="garden-title">{t.title}</h1>
        <p>{t.lead}</p>
      </header>
      {error ? <p className="node__note node__note--warn">{error}</p> : null}
      {items === null && !error ? <span className="spinner" aria-label={t.loading} /> : null}
      {items && !items.length ? (
        <div className="chimeras__empty">
          <p>{t.empty}</p>
          <a className="btn btn--primary" href={hrefFor({ view: "chimeras" })} onClick={linkHandler({ view: "chimeras" })}>
            {t.toChimeras}
          </a>
        </div>
      ) : null}
      <ul className="chimeras__grid" aria-label={t.title}>
        {items?.map((v) => (
          <li key={v.id} className="chimeras__item">
            <CardTile version={v} editable={false} />
            {v.mine ? <p className="garden__mine">{t.mine}</p> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
