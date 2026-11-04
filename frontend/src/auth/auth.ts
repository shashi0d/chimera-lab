import { create } from "zustand";
import { setVisitorIdProvider } from "../api/client";
import { uuid } from "../api/session";

/**
 * No sign-in: this browser is the visitor. A random UUID is made on the first visit and kept in localStorage
 * (no expiry, unlike cookies); every API request sends it as `X-Visitor-Id` (api/client.ts) and the backend
 * keeps the visitor's workspaces, creatures and daily caps under it. Clearing site data starts a new visitor.
 */

export type AuthStatus = "loading" | "signed-out" | "signed-in";

interface AuthState {
  status: AuthStatus;
  userId: string | null;
}

export const useAuth = create<AuthState>()(() => ({ status: "loading", userId: null }));

const STORAGE_KEY = "chimera.visitorId";
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

let visitorId: string | null = null;
setVisitorIdProvider(() => visitorId);

function newId(): string {
  const id = uuid();
  if (UUID_RE.test(id)) return id;
  // Old browsers without crypto.randomUUID: build a v4 UUID from random bytes.
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6]! & 0x0f) | 0x40;
  b[8] = (b[8]! & 0x3f) | 0x80;
  const h = Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

/** This browser's visitor id: the saved one, or a new one saved now. Storage blocked: an id for this tab only. */
function loadVisitorId(): string {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && UUID_RE.test(saved)) return saved.toLowerCase();
    const id = newId();
    localStorage.setItem(STORAGE_KEY, id);
    return id;
  } catch {
    return newId();
  }
}

/** Start the session (once, synchronous): no network, no sign-in screen. */
export function initAuth(): Promise<void> {
  if (!visitorId) {
    visitorId = loadVisitorId();
    useAuth.setState({ status: "signed-in", userId: visitorId });
  }
  return Promise.resolve();
}

/** Tests: set the session state directly. */
export function setTestSession(user: { id: string; email?: string } | null): void {
  visitorId = user?.id ?? null;
  useAuth.setState(user ? { status: "signed-in", userId: user.id } : { status: "signed-out", userId: null });
}
