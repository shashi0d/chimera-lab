import { useReactFlow } from "@xyflow/react";
import { useEffect, useRef, useState } from "react";
import { toAppError } from "../api/errors";
import { presentError } from "../api/errorMessages";
import { copy } from "../copy";
import { useGraph } from "../graph/store";
import { useWorkspaces } from "../persistence/workspaces";
import { openWorkspace } from "../screens/HomePage";
import { Button } from "../ui/Button";
import { Icon } from "../ui/Icon";
import { toast } from "../ui/toastStore";
import { TOUR_STEPS, useTour } from "./tourStore";

/** Start a fresh workspace and open it: the tour's last step. */
export async function startOwnWorkspace(): Promise<void> {
  const ws = await useWorkspaces.getState().create(copy.tour.firstWorkspace);
  useTour.getState().end();
  openWorkspace(ws.id);
}

/** Keep the step's node in view (the canvas mounts a moment after the route changes). */
function useCentreOn(nodeId: string | undefined, step: number): void {
  const flow = useReactFlow();
  useEffect(() => {
    if (!nodeId) return;
    const t = window.setTimeout(() => {
      const n = useGraph.getState().nodes.find((x) => x.id === nodeId);
      if (!n) return;
      try {
        void flow.setCenter(n.position.x + 170, n.position.y + 230, { zoom: 0.8, duration: 300 });
      } catch {
        /* the canvas is not mounted */
      }
    }, 150);
    return () => window.clearTimeout(t);
  }, [flow, nodeId, step]);
}

/** The coach card of the guided tour: what this step shows, Back / Next, Skip. */
export function Tour() {
  const active = useTour((s) => s.active);
  const step = useTour((s) => s.step);
  const [busy, setBusy] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const spec = TOUR_STEPS[step]!;
  useCentreOn(active ? spec.select : undefined, step);

  useEffect(() => {
    if (active) heading.current?.focus();
  }, [active, step]);

  if (!active) return null;
  const text = copy.tour.steps[spec.id];
  const last = step === TOUR_STEPS.length - 1;
  const { go, end } = useTour.getState();

  const start = async () => {
    setBusy(true);
    try {
      await startOwnWorkspace();
    } catch (e) {
      toast.error(presentError(toAppError(e)).title);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section
      className={`tour tour--${spec.id}`}
      aria-labelledby="tour-title"
      onKeyDown={(e) => {
        if (e.key === "Escape") end();
      }}
    >
      <div className="tour__top">
        <ol className="tour__dots" aria-label={copy.tour.progress(step + 1, TOUR_STEPS.length)}>
          {TOUR_STEPS.map((s, n) => (
            <li key={s.id} className={n === step ? "is-current" : n < step ? "is-done" : ""} aria-current={n === step ? "step" : undefined} />
          ))}
        </ol>
        <button type="button" className="tour__skip" onClick={end}>
          {copy.tour.skip}
        </button>
      </div>
      <p className="tour__kicker">
        <Icon name="info" size={14} /> {copy.tour.kicker} · {copy.tour.progress(step + 1, TOUR_STEPS.length)}
      </p>
      <h2 id="tour-title" ref={heading} tabIndex={-1} className="tour__title">
        {text.title}
      </h2>
      <p className="tour__body">{text.body}</p>
      {"points" in text ? (
        <ul className="tour__points">
          {text.points.map((p) => (
            <li key={p.label}>
              <strong>{p.label}</strong> {p.text}
            </li>
          ))}
        </ul>
      ) : null}
      <div className="tour__actions">
        {step > 0 ? (
          <Button size="sm" variant="ghost" icon="left" onClick={() => go(step - 1)}>
            {copy.tour.back}
          </Button>
        ) : null}
        {last ? (
          <Button size="sm" variant="primary" icon="plus" busy={busy} disabled={busy} onClick={() => void start()}>
            {copy.tour.start}
          </Button>
        ) : (
          <Button size="sm" variant="primary" onClick={() => go(step + 1)}>
            {copy.tour.next}
          </Button>
        )}
      </div>
    </section>
  );
}
