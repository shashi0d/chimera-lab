import type { Asset, ErrorEnvelope, Graph, Health, Run, StartRunRequest } from "../types/api";
import { ApiRequestError, fromBody } from "./errors";
import { sessionId } from "./session";

type Listener = (ok: boolean) => void;

export const apiConfig = {
  baseUrl: (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000",
  /** Test hook: forwarded as X-Mock-Fault (the backend ignores it outside mock mode). */
  fault: null as string | null,
};

const networkListeners = new Set<Listener>();
/** Connectivity subscribes here: every request reports whether the network round-trip worked. */
export function onNetworkResult(fn: Listener): () => void {
  networkListeners.add(fn);
  return () => networkListeners.delete(fn);
}
function report(ok: boolean): void {
  networkListeners.forEach((fn) => fn(ok));
}

export function absoluteUrl(url: string): string {
  return /^(https?:|blob:|data:)/.test(url) ? url : `${apiConfig.baseUrl}${url}`;
}

function headers(extra: Record<string, string> = {}): Record<string, string> {
  const h: Record<string, string> = { "X-Session-Id": sessionId(), ...extra };
  if (apiConfig.fault) h["X-Mock-Fault"] = apiConfig.fault;
  return h;
}

async function parseError(res: Response): Promise<ApiRequestError> {
  try {
    const body = (await res.json()) as ErrorEnvelope;
    if (body?.error?.code) return new ApiRequestError(fromBody(body.error), res.status);
  } catch {
    /* fall through */
  }
  return new ApiRequestError({ code: res.status >= 500 ? "INTERNAL" : "UNKNOWN", message: res.statusText, retryable: res.status >= 500 }, res.status);
}

async function request<T>(path: string, init: RequestInit & { timeoutMs?: number } = {}): Promise<{ data: T | null; res: Response }> {
  const controller = new AbortController();
  const timer = init.timeoutMs ? setTimeout(() => controller.abort(), init.timeoutMs) : null;
  if (init.signal) init.signal.addEventListener("abort", () => controller.abort(), { once: true });
  let res: Response;
  try {
    res = await fetch(absoluteUrl(path), { ...init, signal: controller.signal });
  } catch (e) {
    if (init.signal?.aborted) throw e;
    report(false);
    throw new ApiRequestError({ code: "NETWORK", message: "Network request failed.", retryable: true });
  } finally {
    if (timer) clearTimeout(timer);
  }
  report(true);
  if (res.status === 304) return { data: null, res };
  if (!res.ok) throw await parseError(res);
  return { data: (await res.json()) as T, res };
}

export const api = {
  async health(timeoutMs = 5000): Promise<Health> {
    const { data } = await request<Health>("/health", { headers: headers(), timeoutMs });
    return data as Health;
  },

  async startRun(body: StartRunRequest, idempotencyKey: string): Promise<Run> {
    const { data } = await request<Run>("/runs", {
      method: "POST",
      headers: headers({ "Content-Type": "application/json", "Idempotency-Key": idempotencyKey }),
      body: JSON.stringify(body),
    });
    return data as Run;
  },

  /** Returns null when unchanged (304). */
  async getRun(id: string, etag?: string | null): Promise<{ run: Run | null; etag: string | null }> {
    const extra: Record<string, string> = etag ? { "If-None-Match": etag } : {};
    const { data, res } = await request<Run>(`/runs/${encodeURIComponent(id)}`, { headers: headers(extra), timeoutMs: 15000 });
    return { run: data, etag: res.headers.get("ETag") };
  },

  async cancelRun(id: string): Promise<Run> {
    const { data } = await request<Run>(`/runs/${encodeURIComponent(id)}/cancel`, { method: "POST", headers: headers() });
    return data as Run;
  },

  async saveGraph(graph: Graph): Promise<void> {
    await request<Graph>(`/graphs/${encodeURIComponent(graph.graphId)}`, {
      method: "PUT",
      headers: headers({ "Content-Type": "application/json" }),
      body: JSON.stringify(graph),
    });
  },

  async getAsset(id: string): Promise<Asset> {
    const { data } = await request<Asset>(`/assets/${encodeURIComponent(id)}`, { headers: headers() });
    return data as Asset;
  },

  /** XHR so we get upload progress; abort via the returned function. */
  uploadAsset(file: Blob, fileName: string, onProgress: (fraction: number) => void): { promise: Promise<Asset>; abort: () => void } {
    const xhr = new XMLHttpRequest();
    const promise = new Promise<Asset>((resolve, reject) => {
      xhr.open("POST", absoluteUrl("/assets"));
      for (const [k, v] of Object.entries(headers())) xhr.setRequestHeader(k, v);
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) onProgress(e.loaded / e.total);
      };
      xhr.onload = () => {
        report(true);
        let body: unknown = null;
        try {
          body = JSON.parse(xhr.responseText);
        } catch {
          /* non-JSON */
        }
        if (xhr.status >= 200 && xhr.status < 300) resolve(body as Asset);
        else if (body && typeof body === "object" && "error" in body) reject(new ApiRequestError(fromBody((body as ErrorEnvelope).error), xhr.status));
        else reject(new ApiRequestError({ code: "INTERNAL", message: "Upload failed.", retryable: true }, xhr.status));
      };
      xhr.onerror = () => {
        report(false);
        reject(new ApiRequestError({ code: "NETWORK", message: "Network request failed.", retryable: true }));
      };
      xhr.onabort = () => reject(new ApiRequestError({ code: "ABORTED", message: "Upload cancelled.", retryable: true }));
      const form = new FormData();
      form.append("file", file, fileName);
      xhr.send(form);
    });
    return { promise, abort: () => xhr.abort() };
  },
};
