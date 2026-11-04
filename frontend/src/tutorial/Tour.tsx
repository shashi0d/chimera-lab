import { useEffect, useRef } from "react";
import { navigate, useRoute } from "../app/route";
import { copy } from "../copy";
import { isTerminal, useRun } from "../evo/runs";
import { useGraph } from "../graph/store";
import type { FusionData } from "../nodes/fusion/types";
import type { VersionData } from "../nodes/version/types";
import { useWorkspaces } from "../persistence/workspaces";
import { Button } from "../ui/Button";
import { Icon } from "../ui/Icon";
import { TUTORIAL_WS, tutorialVersion } from "./sandbox";
import { useTour } from "./tourStore";

/** Back to the tutorial canvas (left it in the middle). */
function openTutorial(): void {
  useWorkspaces.getState().open(TUTORIAL_WS);
  navigate({ view: "lab", runId: null, workspaceId: TUTORIAL_WS });
}

export type TourStep = keyof typeof copy.tour.steps;

/** The order the dots show. */
const ORDER: TourStep[] = ["add-fusion", "make", "wait", "save", "open-chimeras", "chimeras", "nav-workspaces", "new-workspace"];

/** What each step makes glow (the element carrying data-tour="…"). Null: nothing to click, just watch. */
const TARGET: Record<TourStep, string | null> = {
  "add-fusion": "add-fusion",
  make: "make",
  wait: null,
  save: "save",
  "open-chimeras": "nav-chimeras",
  chimeras: "chimera-tutorial",
  "nav-workspaces": "nav-workspaces",
  "new-workspace": "new-workspace",
  return: null,
};

/** The current step, read from what is on screen: the tutorial canvas, its run, the page. */
function useStep(): { step: TourStep | null; versionNodeId: string | null } {
  const active = useTour((s) => s.active);
  const phase = useTour((s) => s.phase);
  const route = useRoute();
  const inTutorial = useWorkspaces((s) => s.currentId === TUTORIAL_WS) && route.view === "lab";
  const fusion = useGraph((s) => s.nodes.find((n) => n.type === "fusion"));
  const versionNode = useGraph((s) => s.nodes.find((n) => n.type === "version" && (n.data as VersionData).version));
  const run = useRun((fusion?.data as FusionData | undefined)?.activeRunId ?? null);
  if (!active) return { step: null, versionNodeId: null };
  if (phase === "workspaces") return { step: route.view === "home" ? "new-workspace" : "nav-workspaces", versionNodeId: null };
  if (phase === "chimeras") return { step: "chimeras", versionNodeId: null };
  if (route.view === "chimeras") return { step: "chimeras", versionNodeId: null };
  if (!inTutorial) return { step: tutorialVersion().saved ? "open-chimeras" : "return", versionNodeId: null };
  const version = versionNode ? (versionNode.data as VersionData).version : null;
  if (version) return { step: version.saved ? "open-chimeras" : "save", versionNodeId: versionNode!.id };
  if (!fusion) return { step: "add-fusion", versionNodeId: null };
  if (run && !isTerminal(run.status)) return { step: "wait", versionNodeId: null };
  if (run?.status === "succeeded") return { step: "wait", versionNodeId: null }; // the image card is on its way
  return { step: "make", versionNodeId: null };
}

/** The coach card: what to do now, the glowing target, and Skip (back to the workspace list). */
export function Tour() {
  const { step, versionNodeId } = useStep();
  const phase = useTour((s) => s.phase);
  const route = useRoute();
  const heading = useRef<HTMLHeadingElement>(null);

  // Reaching Chimeras moves the tour on from the Lab.
  useEffect(() => {
    if (step === "chimeras" && phase === "lab") useTour.getState().setPhase("chimeras");
  }, [step, phase]);

  // The Save step selects the image card, so its toolbar (and the tools panel) show the Save button.
  useEffect(() => {
    if (step !== "save" || !versionNodeId) return;
    const g = useGraph.getState();
    if (!g.selection.includes(versionNodeId)) g.setSelection([versionNodeId]);
  }, [step, versionNodeId]);

  // Make the target glow (CSS: [data-tour-target="x"] [data-tour="x"]).
  useEffect(() => {
    const root = document.documentElement;
    const target = step ? TARGET[step] : null;
    if (target) root.dataset.tourTarget = target;
    else delete root.dataset.tourTarget;
    return () => {
      delete root.dataset.tourTarget;
    };
  }, [step]);

  useEffect(() => {
    if (step) heading.current?.focus({ preventScroll: true });
  }, [step]);

  if (!step) return null;
  const text = copy.tour.steps[step];
  const dots = ORDER;
  const n = Math.max(0, (ORDER as string[]).indexOf(step));
  const { end, setPhase } = useTour.getState();

  return (
    <section className={`tour tour--${step}${route.view === "lab" ? " tour--lab" : ""}`} aria-labelledby="tour-title" aria-live="polite">
      <div className="tour__top">
        <ol className="tour__dots" aria-label={copy.tour.progress(n + 1, dots.length)}>
          {dots.map((s, i) => (
            <li key={s} className={i === n ? "is-current" : i < n ? "is-done" : ""} aria-current={i === n ? "step" : undefined} />
          ))}
        </ol>
        <button type="button" className="tour__skip" onClick={() => end({ skipped: true })}>
          {copy.tour.skip}
        </button>
      </div>
      <p className="tour__kicker">
        <Icon name="info" size={14} /> {copy.tour.kicker} · {copy.tour.progress(n + 1, dots.length)}
      </p>
      <h2 id="tour-title" ref={heading} tabIndex={-1} className="tour__title">
        {text.title}
      </h2>
      <p className="tour__body">{text.body}</p>
      {step === "wait" ? (
        <p className="tour__hint">
          <span className="spinner spinner--inline" aria-hidden="true" /> {copy.tour.steps.wait.title}…
        </p>
      ) : TARGET[step] && step !== "chimeras" ? (
        <p className="tour__hint">
          <Icon name="right" size={14} /> {copy.tour.clickHint}
        </p>
      ) : null}
      {step === "return" ? (
        <div className="tour__actions">
          <Button size="sm" variant="primary" icon="right" onClick={() => openTutorial()}>
            {copy.tour.backToTutorial}
          </Button>
        </div>
      ) : null}
      {step === "chimeras" ? (
        <div className="tour__actions">
          <Button size="sm" variant="primary" icon="right" onClick={() => setPhase("workspaces")}>
            {copy.tour.next}
          </Button>
        </div>
      ) : null}
    </section>
  );
}
