import { httpDevConfig, httpTransport } from "./http";
import type { EvoTransport } from "./transport";

/**
 * The transport the app talks to. Production builds always use the real one (relative /evo/... URLs, same
 * origin). Dev and test builds use the fixture-backed mock unless VITE_EVO_TRANSPORT=http, in which case
 * ?mock=<scenario> is forwarded to a mock-mode backend as X-Mock-Scenario instead.
 */
let current: EvoTransport = httpTransport;

export function evo(): EvoTransport {
  return current;
}

export function setTransport(t: EvoTransport): void {
  current = t;
}

const MOCK_KEY = "chimera.mock.params";

/** Mock parameters from the URL (?mock=, ?mockStep=, ?mockHold=), kept for the tab so a reload replays the same run. */
function mockParams(): { mock?: string; mockStep?: string; mockHold?: string } {
  const params = new URLSearchParams(window.location.search);
  let stored: Record<string, string> = {};
  try {
    stored = JSON.parse(sessionStorage.getItem(MOCK_KEY) ?? "{}") as Record<string, string>;
  } catch {
    /* storage blocked */
  }
  for (const k of ["mock", "mockStep", "mockHold"]) {
    const v = params.get(k);
    if (v !== null) stored[k] = v;
  }
  try {
    sessionStorage.setItem(MOCK_KEY, JSON.stringify(stored));
  } catch {
    /* ignore */
  }
  return stored;
}

/** Picks the transport before the app renders. Resolves immediately in production. */
export async function initTransport(): Promise<void> {
  if (import.meta.env.PROD) return;
  const p = mockParams();
  if (import.meta.env.VITE_EVO_TRANSPORT === "http") {
    httpDevConfig.mockScenario = p.mock ?? null;
    return;
  }
  const m = await import("./mock");
  if (m.isMockScenario(p.mock)) m.mockConfig.scenario = p.mock;
  const step = Number(p.mockStep);
  if (Number.isFinite(step) && step > 0) m.mockConfig.stepMs = step;
  if (p.mockHold !== undefined && p.mockHold !== "" && Number.isFinite(Number(p.mockHold))) m.mockConfig.holdAt = Number(p.mockHold);
  setTransport(m.mockTransport);
}
