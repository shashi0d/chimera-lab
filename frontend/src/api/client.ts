import type { ErrorEnvelope } from "../types/api";
import { ApiRequestError, fromBody } from "./errors";

type Listener = (ok: boolean) => void;

export const apiConfig = {
  /** Same origin in production (the backend serves the built frontend at / and the API under /evo). */
  baseUrl: (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "",
};

const networkListeners = new Set<Listener>();
/** Connectivity subscribes here: every request reports whether the network round-trip worked. */
export function onNetworkResult(fn: Listener): () => void {
  networkListeners.add(fn);
  return () => networkListeners.delete(fn);
}
export function reportNetwork(ok: boolean): void {
  networkListeners.forEach((fn) => fn(ok));
}

export function absoluteUrl(url: string): string {
  return /^(https?:|blob:|data:)/.test(url) ? url : `${apiConfig.baseUrl}${url}`;
}

let tokenProvider: () => string | null = () => null;

/** The auth module installs this: the signed-in user's current access token (refreshed by Supabase). */
export function setAccessTokenProvider(fn: () => string | null): void {
  tokenProvider = fn;
}

/** Every request carries the signed-in user's access token, when there is one. */
export function baseHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = tokenProvider();
  return token ? { Authorization: `Bearer ${token}`, ...extra } : { ...extra };
}

export async function parseError(res: Response): Promise<ApiRequestError> {
  try {
    const body = (await res.json()) as ErrorEnvelope;
    if (body?.error?.code) {
      const err = fromBody(body.error);
      const retryAfter = res.headers.get("Retry-After");
      if (err.retryAfterMs == null && retryAfter && Number.isFinite(Number(retryAfter))) err.retryAfterMs = Number(retryAfter) * 1000;
      return new ApiRequestError(err, res.status);
    }
  } catch {
    /* fall through */
  }
  if (res.status === 404) return new ApiRequestError({ code: "NOT_FOUND", message: res.statusText, retryable: false }, res.status);
  return new ApiRequestError({ code: res.status >= 500 ? "INTERNAL" : "UNKNOWN", message: res.statusText, retryable: res.status >= 500 }, res.status);
}

export async function request<T>(path: string, init: RequestInit & { timeoutMs?: number } = {}): Promise<{ data: T; res: Response }> {
  const controller = new AbortController();
  const timer = init.timeoutMs ? setTimeout(() => controller.abort(), init.timeoutMs) : null;
  if (init.signal) init.signal.addEventListener("abort", () => controller.abort(), { once: true });
  let res: Response;
  try {
    res = await fetch(absoluteUrl(path), { ...init, signal: controller.signal });
  } catch (e) {
    if (init.signal?.aborted) throw e;
    reportNetwork(false);
    throw new ApiRequestError({ code: "NETWORK", message: "Network request failed.", retryable: true });
  } finally {
    if (timer) clearTimeout(timer);
  }
  reportNetwork(true);
  if (!res.ok) throw await parseError(res);
  return { data: (await res.json()) as T, res };
}
