import { api } from "../api/client";
import { toAppError, type AppError } from "../api/errors";
import { useConnectivity } from "../connectivity/store";
import type { Run } from "../types/api";

export const TERMINAL: ReadonlySet<Run["status"]> = new Set(["succeeded", "failed", "cancelled", "interrupted"]);

export interface RunSubscription {
  stop(): void;
}

export interface RunTransport {
  /** Calls onUpdate with each changed Run until it is terminal or stopped. */
  watch(runId: string, onUpdate: (run: Run) => void, onError: (err: AppError) => void): RunSubscription;
}

export const POLL = { fastMs: 1500, slowMs: 5000, slowAfterMs: 60_000 };

/**
 * v1 transport: polls GET /runs/{id} every 1.5s, backing off to 5s after 60s,
 * using ETags so unchanged state isn't re-sent. Pauses while offline or the
 * server is unreachable and resumes on reconnect (the run keeps going server-side).
 */
export const pollingTransport: RunTransport = {
  watch(runId, onUpdate, onError) {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let etag: string | null = null;
    const started = Date.now();
    let unsubConn: (() => void) | null = null;

    const schedule = () => {
      if (stopped) return;
      const delay = Date.now() - started > POLL.slowAfterMs ? POLL.slowMs : POLL.fastMs;
      timer = setTimeout(tick, delay);
    };

    const waitForConnection = () => {
      unsubConn = useConnectivity.subscribe((s) => {
        if (s.status === "online" && !stopped) {
          unsubConn?.();
          unsubConn = null;
          void tick();
        }
      });
    };

    const tick = async () => {
      timer = null;
      if (stopped) return;
      if (useConnectivity.getState().status !== "online") {
        waitForConnection();
        return;
      }
      try {
        const res = await api.getRun(runId, etag);
        if (stopped) return;
        if (res.run) {
          etag = res.etag;
          onUpdate(res.run);
          if (TERMINAL.has(res.run.status)) return;
        }
        schedule();
      } catch (e) {
        if (stopped) return;
        const err = toAppError(e);
        if (err.code === "NETWORK") {
          waitForConnection();
          return;
        }
        onError(err);
        if (err.code !== "RUN_NOT_FOUND") schedule();
      }
    };

    void tick();
    return {
      stop() {
        stopped = true;
        if (timer) clearTimeout(timer);
        unsubConn?.();
      },
    };
  },
};
