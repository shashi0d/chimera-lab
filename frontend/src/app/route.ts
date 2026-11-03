import { useSyncExternalStore } from "react";

// Query-string routes on "/" so the same-origin backend needs no SPA fallback:
//   /                     gallery (the first screen)
//   /?view=lab            the canvas (make a new creature)
//   /?run=<runId>         the canvas with the live trace of that run (reload resumes it)
//   /?creature=<id>       one creature's card (showcase, or your own Fusion run)
//   /?creation=<id>       a published creation and the path that made it

export type Route =
  | { view: "gallery" }
  | { view: "lab"; runId: string | null }
  | { view: "creature"; creatureId: string }
  | { view: "creation"; publicationId: string };

export function parseRoute(search: string): Route {
  const q = new URLSearchParams(search);
  const creation = q.get("creation");
  if (creation) return { view: "creation", publicationId: creation };
  const creature = q.get("creature");
  if (creature) return { view: "creature", creatureId: creature };
  const run = q.get("run");
  if (run) return { view: "lab", runId: run };
  if (q.get("view") === "lab") return { view: "lab", runId: null };
  return { view: "gallery" };
}

export function hrefFor(r: Route): string {
  switch (r.view) {
    case "gallery":
      return "/";
    case "lab":
      return r.runId ? `/?run=${encodeURIComponent(r.runId)}` : "/?view=lab";
    case "creature":
      return `/?creature=${encodeURIComponent(r.creatureId)}`;
    case "creation":
      return `/?creation=${encodeURIComponent(r.publicationId)}`;
  }
}

const subs = new Set<() => void>();
let current = typeof window === "undefined" ? "" : window.location.search;

function sync() {
  if (window.location.search === current) return;
  current = window.location.search;
  subs.forEach((f) => f());
}

if (typeof window !== "undefined") window.addEventListener("popstate", sync);

export function navigate(r: Route, opts: { replace?: boolean } = {}): void {
  const href = hrefFor(r);
  if (href === `${window.location.pathname}${window.location.search}`) return;
  if (opts.replace) window.history.replaceState(null, "", href);
  else window.history.pushState(null, "", href);
  sync();
  window.scrollTo?.(0, 0);
}

let cachedSearch: string | null = null;
let cachedRoute: Route = { view: "gallery" };
function snapshot(): Route {
  const s = typeof window === "undefined" ? "" : window.location.search;
  if (s !== cachedSearch) {
    cachedSearch = s;
    cachedRoute = parseRoute(s);
  }
  return cachedRoute;
}

export function useRoute(): Route {
  return useSyncExternalStore(
    (f) => {
      subs.add(f);
      return () => subs.delete(f);
    },
    snapshot,
    snapshot,
  );
}

/** Click handler for in-app links: plain left clicks navigate in place; modified clicks open as usual. */
export function linkHandler(r: Route) {
  return (e: { button: number; metaKey: boolean; ctrlKey: boolean; shiftKey: boolean; altKey: boolean; preventDefault(): void }) => {
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    navigate(r);
  };
}
