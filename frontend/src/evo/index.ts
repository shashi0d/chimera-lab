import { httpTransport } from "./http";
import type { EvoTransport } from "./transport";

/** The transport the app talks to: the live agent API (relative /evo/... URLs, same origin). Tests swap in a fake. */
let current: EvoTransport = httpTransport;

export function evo(): EvoTransport {
  return current;
}

export function setTransport(t: EvoTransport): void {
  current = t;
}
