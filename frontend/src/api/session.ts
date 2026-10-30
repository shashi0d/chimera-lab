const KEY = "chimera.session";

function randomId(): string {
  const bytes = new Uint8Array(12);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

let cached: string | null = null;

/** Anonymous session id (v1 has no accounts). */
export function sessionId(): string {
  if (cached) return cached;
  try {
    cached = localStorage.getItem(KEY);
    if (!cached) {
      cached = randomId();
      localStorage.setItem(KEY, cached);
    }
  } catch {
    cached = randomId();
  }
  return cached;
}

export function uuid(): string {
  return typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${randomId()}-${Date.now()}`;
}
