import { withTutorial } from "../tutorial/sandbox";
import { httpTransport } from "./http";
import type { EvoTransport } from "./transport";

/**
 * The transport the app talks to: the live agent API (relative /evo/... URLs, same origin), with the tutorial's
 * Fusion run answered locally (tutorial/sandbox.ts). Tests swap in a fake; the tutorial still works on top of it.
 */
let current: EvoTransport = withTutorial(httpTransport);

export function evo(): EvoTransport {
  return current;
}

export function setTransport(t: EvoTransport): void {
  current = withTutorial(t);
}
