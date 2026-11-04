import { useEffect, useRef, useState } from "react";
import { copy } from "../copy";
import { useTour } from "../tutorial/tourStore";
import { Button } from "../ui/Button";

const SEEN_KEY = "chimera.intro";
/** When the buttons are in (the CSS timeline in theme.css, "Intro"). */
const DONE_MS = 4200;

export function hasSeenIntro(): boolean {
  try {
    return localStorage.getItem(SEEN_KEY) === "1";
  } catch {
    return false;
  }
}

function markSeen(): void {
  try {
    localStorage.setItem(SEEN_KEY, "1");
  } catch {
    /* it may show again next visit */
  }
}

/**
 * The welcome screen of a first visit: two animals slide in, glitch into one creature (comic-book halftone, colour
 * split, sliced frames), the title drops with the logo, the tagline lands, then: the tutorial, or the workspaces.
 * A click or a key during the animation jumps to the end; reduced motion shows the end at once.
 */
export function Intro({ onClose }: { onClose(): void }) {
  const [fast, setFast] = useState(false);
  const [ready, setReady] = useState(false);
  const primary = useRef<HTMLButtonElement>(null);
  const t = copy.intro;

  useEffect(() => {
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const id = window.setTimeout(() => setReady(true), reduce || fast ? 0 : DONE_MS);
    return () => window.clearTimeout(id);
  }, [fast]);

  useEffect(() => {
    if (ready) primary.current?.focus();
  }, [ready]);

  useEffect(() => {
    if (ready) return;
    const onKey = () => setFast(true);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [ready]);

  const tutorial = () => {
    markSeen();
    onClose();
    void useTour.getState().start();
  };
  const workspaces = () => {
    markSeen();
    onClose();
    useTour.getState().end({ skipped: true });
  };

  return (
    <div className={`intro${fast ? " is-fast" : ""}${ready ? " is-ready" : ""}`} role="dialog" aria-modal="true" aria-labelledby="intro-title" onClick={() => !ready && setFast(true)}>
      {/* Print inks for the colour split: white turns transparent, dark turns cyan or magenta. */}
      <svg className="intro__inks" aria-hidden="true" focusable="false">
        <filter id="intro-ink-cyan" colorInterpolationFilters="sRGB">
          <feColorMatrix type="matrix" values="0 0 0 0 0  0 0 0 0 0.72  0 0 0 0 1  -0.62 -0.62 -0.62 1.62 0" />
        </filter>
        <filter id="intro-ink-magenta" colorInterpolationFilters="sRGB">
          <feColorMatrix type="matrix" values="0 0 0 0 1  0 0 0 0 0.18  0 0 0 0 0.58  -0.62 -0.62 -0.62 1.62 0" />
        </filter>
      </svg>
      <div className="intro__halftone" aria-hidden="true" />
      <div className="intro__lines" aria-hidden="true" />
      <div className="intro__stage" aria-hidden="true">
        <figure className="intro__animal intro__animal--a">
          <img src="/intro/tiger.webp" alt="" decoding="async" />
          <figcaption>{t.animalA}</figcaption>
        </figure>
        <figure className="intro__animal intro__animal--b">
          <img src="/intro/bat.webp" alt="" decoding="async" />
          <figcaption>{t.animalB}</figcaption>
        </figure>
        <span className="intro__flash" />
        <div className="intro__chimera">
          <img className="intro__layer intro__layer--cyan" src="/intro/chimera.webp" alt="" decoding="async" />
          <img className="intro__layer intro__layer--magenta" src="/intro/chimera.webp" alt="" decoding="async" />
          <img className="intro__layer intro__layer--slice" src="/intro/chimera.webp" alt="" decoding="async" />
          <img className="intro__layer intro__layer--main" src="/intro/chimera.webp" alt="" decoding="async" />
        </div>
      </div>
      <div className="intro__text">
        <p className="intro__welcome">{t.welcome}</p>
        <div className="intro__title">
          <span className="intro__logo brand__mark" aria-hidden="true">
            <svg viewBox="0 0 32 32" focusable="false">
              <path d="M7.5 21.5c2.2-6.4 5.6-9.6 8.5-9.6s6.3 3.2 8.5 9.6" className="brand__arc" />
              <circle cx="10.5" cy="11.5" r="3" className="brand__a" />
              <path d="M21.5 8.2l3.3 3.3-3.3 3.3-3.3-3.3z" className="brand__b" />
            </svg>
          </span>
          <h1 id="intro-title" data-text={copy.app.name}>
            {copy.app.name}
          </h1>
        </div>
        <p className="intro__tagline">{t.tagline}</p>
        <div className="intro__actions">
          <Button ref={primary} variant="primary" icon="help" onClick={tutorial} disabled={!ready}>
            {t.tutorial}
          </Button>
          <Button variant="secondary" icon="right" onClick={workspaces} disabled={!ready}>
            {t.workspaces}
          </Button>
        </div>
        {ready ? null : <p className="intro__hint">{t.skipHint}</p>}
      </div>
    </div>
  );
}
