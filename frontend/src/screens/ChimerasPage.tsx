import { useCallback, useEffect, useState } from "react";
import { toAppError } from "../api/errors";
import { presentError } from "../api/errorMessages";
import { linkHandler, hrefFor } from "../app/route";
import { useAuth } from "../auth/auth";
import { isTutorialId } from "../tutorial/sandbox";
import { CardTile } from "../lab/CardTile";
import { labApi, type LabVersion } from "../lab/api";
import { Button } from "../ui/Button";
import { toast } from "../ui/toastStore";

const POLL_MS = 4000;

/** Every saved creature with its animal card (tap a card to open it). Cards still being drawn fill in by themselves. */
export function ChimerasPage() {
  const status = useAuth((s) => s.status);
  const [items, setItems] = useState<LabVersion[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setItems(await labApi.chimeras());
      setError(null);
    } catch (e) {
      setError(presentError(toAppError(e)).title);
    }
  }, []);

  useEffect(() => {
    if (status === "signed-in") void load();
  }, [status, load]);

  const drawing = Boolean(items?.some((v) => v.card?.status === "running"));
  useEffect(() => {
    if (!drawing) return;
    const id = window.setInterval(() => void load(), POLL_MS);
    return () => window.clearInterval(id);
  }, [drawing, load]);

  const replace = (v: LabVersion) => setItems((list) => list?.map((x) => (x.id === v.id ? { ...x, ...v } : x)) ?? null);
  const unsave = async (v: LabVersion) => {
    try {
      await labApi.setSaved(v.id, false);
      setItems((list) => list?.filter((x) => x.id !== v.id) ?? null);
    } catch (e) {
      toast.error(presentError(toAppError(e)).title);
    }
  };
  const share = async (v: LabVersion) => {
    try {
      const next = await labApi.setShared(v.id, !v.shared);
      replace(next);
      toast.success(next.shared ? `${next.title ?? "Your creature"} is in the Garden now.` : "Taken out of the Garden.");
    } catch (e) {
      toast.error(presentError(toAppError(e)).title);
    }
  };
  const retry = async (v: LabVersion) => {
    try {
      const card = await labApi.card(v.id);
      replace({ ...v, card });
    } catch (e) {
      toast.error(presentError(toAppError(e)).title);
    }
  };

  return (
    <section className="chimeras" aria-labelledby="chimeras-title">
      <header className="chimeras__head">
        <h1 id="chimeras-title">Chimeras</h1>
        <p>Every creature you saved. Click a card to open its field-guide page; edit its text from the open card.</p>
      </header>
      {error ? <p className="node__note node__note--warn">{error}</p> : null}
      {items === null && !error ? <span className="spinner" aria-label="Loading your chimeras" /> : null}
      {items && !items.length ? (
        <div className="chimeras__empty">
          <p>No saved creatures yet. In the Lab, use Save on any image card: its animal card is made in the background.</p>
          <a className="btn btn--primary" href={hrefFor({ view: "home" })} onClick={linkHandler({ view: "home" })}>
            Go to your workspaces
          </a>
        </div>
      ) : null}
      <ul className="chimeras__grid">
        {items?.map((v) => (
          <li key={v.id} className="chimeras__item" data-tour={isTutorialId(v.id) ? "chimera-tutorial" : undefined}>
            <CardTile version={v} onChange={replace} editable={!isTutorialId(v.id)} />
            <div className="chimeras__actions">
              <Button size="sm" variant={v.shared ? "secondary" : "primary"} icon="globe" aria-pressed={Boolean(v.shared)} onClick={() => void share(v)}>
                {v.shared ? "In the Garden ✓" : "Share to Garden"}
              </Button>
              {v.card?.status === "failed" || !v.card ? (
                <Button size="sm" variant="secondary" icon="refresh" onClick={() => void retry(v)}>
                  Make the card again
                </Button>
              ) : null}
              <Button size="sm" variant="ghost" icon="close" onClick={() => void unsave(v)}>
                Remove from chimeras
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
