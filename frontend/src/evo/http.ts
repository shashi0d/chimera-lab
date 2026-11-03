import { absoluteUrl, baseHeaders, parseError, reportNetwork, request } from "../api/client";
import { ApiRequestError, toAppError } from "../api/errors";
import { SseParser } from "./sse";
import type { EventStream, EvoTransport, StreamHandlers } from "./transport";
import { EVENT_TYPES, isTerminalEvent, type AgentEvent, type Creature, type GalleryPage, type Health, type Limits, type Publication, type RunSnapshot, type StartInput, type StartResult } from "./types";

const TERMINAL_STATUS = new Set(["succeeded", "failed", "interrupted"]);
export const STREAM = { backoffMs: [1000, 2000, 4000, 8000, 15000], idleMs: 45_000 };

function headers(extra: Record<string, string> = {}): Record<string, string> {
  return baseHeaders(extra);
}

const enc = encodeURIComponent;

/** Parse one SSE data payload into an event; anything that isn't a known event is ignored. */
export function toEvent(data: string): AgentEvent | null {
  try {
    const e = JSON.parse(data) as AgentEvent;
    return e && typeof e.id === "number" && EVENT_TYPES.has(e.type) ? e : null;
  } catch {
    return null;
  }
}

/**
 * Reads GET /evo/agent/runs/{id}/events with fetch (EventSource can't send the Authorization header).
 * Resumes with Last-Event-ID and ?after=, reconnects with backoff, and treats 45 s without a byte
 * (the server pings every 15 s) as a dead connection.
 */
export function streamRunEvents(
  runId: string,
  after: number,
  h: StreamHandlers,
  deps: { fetch: typeof fetch; getRun: (id: string) => Promise<RunSnapshot> } = { fetch: (...a) => fetch(...a), getRun: (id) => httpTransport.getRun(id) },
): EventStream {
  let last = after;
  let stopped = false;
  let attempt = 0;
  let controller: AbortController | null = null;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;

  const finish = () => {
    stopped = true;
    h.onState?.("closed");
  };

  const scheduleRetry = () => {
    if (stopped) return;
    h.onState?.("reconnecting");
    const delay = STREAM.backoffMs[Math.min(attempt, STREAM.backoffMs.length - 1)]!;
    attempt += 1;
    const go = () => {
      retryTimer = null;
      if (typeof navigator !== "undefined" && navigator.onLine === false) {
        const onOnline = () => {
          window.removeEventListener("online", onOnline);
          void connect();
        };
        window.addEventListener("online", onOnline);
        return;
      }
      void connect();
    };
    retryTimer = setTimeout(go, delay);
  };

  const connect = async () => {
    if (stopped) return;
    h.onState?.(attempt === 0 ? "connecting" : "reconnecting");
    controller = new AbortController();
    let idle: ReturnType<typeof setTimeout> | null = null;
    const arm = () => {
      if (idle) clearTimeout(idle);
      idle = setTimeout(() => controller?.abort(), STREAM.idleMs);
    };
    let received = 0;
    try {
      const res = await deps.fetch(absoluteUrl(`/evo/agent/runs/${enc(runId)}/events?after=${last}`), {
        headers: headers({ Accept: "text/event-stream", "Last-Event-ID": String(last) }),
        signal: controller.signal,
        cache: "no-store",
      });
      reportNetwork(true);
      if (!res.ok) {
        const err = await parseError(res);
        if (res.status === 404 || !err.retryable) {
          h.onError?.(err.toJSON());
          finish();
          return;
        }
        scheduleRetry();
        return;
      }
      if (!res.body) throw new Error("no body");
      h.onState?.("open");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      const parser = new SseParser();
      arm();
      for (;;) {
        const { value, done } = await reader.read();
        if (done || stopped) break;
        arm();
        for (const msg of parser.push(decoder.decode(value, { stream: true }))) {
          const e = toEvent(msg.data);
          if (!e || e.id <= last) continue;
          last = e.id;
          received += 1;
          attempt = 0;
          h.onEvent(e);
          if (isTerminalEvent(e)) {
            if (idle) clearTimeout(idle);
            controller.abort();
            finish();
            return;
          }
        }
      }
    } catch (e) {
      if (stopped) return;
      if (!(e instanceof DOMException && e.name === "AbortError")) reportNetwork(false);
    } finally {
      if (idle) clearTimeout(idle);
    }
    if (stopped) return;
    // The stream ended without a terminal event. If nothing new came, check whether the run is over.
    if (received === 0 && attempt > 0) {
      try {
        const snap = await deps.getRun(runId);
        if (TERMINAL_STATUS.has(snap.status) && snap.lastEventId <= last) {
          finish();
          return;
        }
      } catch (err) {
        const appErr = toAppError(err);
        if (appErr.code === "RUN_NOT_FOUND" || appErr.code === "NOT_FOUND") {
          h.onError?.(appErr);
          finish();
          return;
        }
      }
    }
    scheduleRetry();
  };

  void connect();
  return {
    stop() {
      stopped = true;
      if (retryTimer) clearTimeout(retryTimer);
      controller?.abort();
    },
  };
}

export const httpTransport: EvoTransport = {
  kind: "http",

  async health() {
    const { data } = await request<Health>("/health", { headers: headers(), timeoutMs: 5000 });
    return { status: data?.status ?? "ok" };
  },

  async startRun(input: StartInput): Promise<StartResult> {
    const form = new FormData();
    form.append("mode", input.mode);
    if (input.sireImage) form.append("sireImage", input.sireImage, "sire.jpg");
    if (input.damImage) form.append("damImage", input.damImage, "dam.jpg");
    if (input.sireName) form.append("sireName", input.sireName);
    if (input.damName) form.append("damName", input.damName);
    const { data, res } = await request<StartResult & { status: string }>("/evo/agent/runs", { method: "POST", headers: headers(), body: form });
    if (res.status === 200 && data.status === "needs_choice") return { ...(data as object), kind: "identify" } as StartResult;
    return { ...(data as object), kind: "accepted" } as StartResult;
  },

  async getRun(runId) {
    try {
      const { data } = await request<RunSnapshot>(`/evo/agent/runs/${enc(runId)}`, { headers: headers(), timeoutMs: 15000 });
      return data;
    } catch (e) {
      if (e instanceof ApiRequestError && e.status === 404 && e.code === "NOT_FOUND") {
        throw new ApiRequestError({ code: "RUN_NOT_FOUND", message: e.message, retryable: false }, 404);
      }
      throw e;
    }
  },

  streamEvents(runId, after, handlers) {
    return streamRunEvents(runId, after, handlers);
  },

  async postChoice(runId, choiceId, answer) {
    await request<{ accepted: boolean }>(`/evo/agent/runs/${enc(runId)}/choice`, {
      method: "POST",
      headers: headers({ "Content-Type": "application/json" }),
      body: JSON.stringify({ choiceId, answer }),
    });
  },

  async getLimits() {
    const { data } = await request<Limits>("/evo/agent/limits", { headers: headers(), timeoutMs: 10000 });
    return data;
  },

  async getCreature(id) {
    const { data } = await request<Creature>(`/evo/creatures/${enc(id)}`, { headers: headers(), timeoutMs: 15000 });
    return data;
  },

  async getPublication(id) {
    const { data } = await request<Publication>(`/evo/publications/${enc(id)}`, { headers: headers(), timeoutMs: 15000 });
    return data;
  },

  async getGallery(cursor, limit = 24) {
    const q = new URLSearchParams({ limit: String(limit) });
    if (cursor) q.set("cursor", cursor);
    const { data } = await request<GalleryPage>(`/evo/gallery?${q.toString()}`, { headers: headers(), timeoutMs: 15000 });
    return data;
  },

  imageUrl(url) {
    return absoluteUrl(url);
  },
};
