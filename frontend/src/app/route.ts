import { useSyncExternalStore } from "react";

// Query-string routes on "/" so the same-origin backend needs no SPA fallback:
//   /                          the home page: every workspace, and New workspace (the first screen)
//   /?ws=<id>                  that workspace's canvas
//   /?ws=<id>&run=<runId>      the canvas, following that run (reload resumes it)
//   /?view=chimeras            the saved creatures, each with its animal card

export type Route =
  | { view: "home" }
  | { view: "lab"; runId: string | null; workspaceId?: string | null }
  | { view: "chimeras" };

export function parseRoute(search: string): Route {
  const q = new URLSearchParams(search);
  if (q.get("view") === "chimeras") return { view: "chimeras" };
  const ws = q.get("ws");
  const run = q.get("run");
  if (ws || run) return { view: "lab", runId: run, workspaceId: ws };
  return { view: "home" };
}

export function hrefFor(r: Route): string {
  switch (r.view) {
    case "home":
      return "/";
    case "chimeras":
      return "/?view=chimeras";
    case "lab": {
      const q = new URLSearchParams();
      if (r.workspaceId) q.set("ws", r.workspaceId);
      if (r.runId) q.set("run", r.runId);
      const s = q.toString();
      return s ? `/?${s}` : "/";
    }
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
let cachedRoute: Route = { view: "home" };
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
