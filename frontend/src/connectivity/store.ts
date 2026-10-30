import { create } from "zustand";
import { api, onNetworkResult } from "../api/client";

export type ConnectivityStatus = "online" | "offline" | "unreachable";

interface ConnectivityState {
  browserOnline: boolean;
  serverReachable: boolean;
  /** Test hook: pin a status regardless of reality. */
  forced: ConnectivityStatus | null;
  status: ConnectivityStatus;
  mode: "mock" | "real" | null;
  lastCheckedAt: number | null;
  setBrowserOnline(v: boolean): void;
  setServerReachable(v: boolean): void;
  force(s: ConnectivityStatus | null): void;
  check(): Promise<ConnectivityStatus>;
}

function derive(s: Pick<ConnectivityState, "browserOnline" | "serverReachable" | "forced">): ConnectivityStatus {
  if (s.forced) return s.forced;
  if (!s.browserOnline) return "offline";
  return s.serverReachable ? "online" : "unreachable";
}

let inflight: Promise<ConnectivityStatus> | null = null;

export const useConnectivity = create<ConnectivityState>()((set, get) => ({
  browserOnline: typeof navigator === "undefined" ? true : navigator.onLine,
  serverReachable: true,
  forced: null,
  status: "online",
  mode: null,
  lastCheckedAt: null,
  setBrowserOnline(v) {
    set((s) => ({ browserOnline: v, status: derive({ ...s, browserOnline: v }) }));
  },
  setServerReachable(v) {
    set((s) => ({ serverReachable: v, status: derive({ ...s, serverReachable: v }) }));
  },
  force(forced) {
    set((s) => ({ forced, status: derive({ ...s, forced }) }));
  },
  async check() {
    if (inflight) return inflight;
    inflight = (async () => {
      try {
        const h = await api.health();
        set({ mode: h.mode });
        get().setServerReachable(true);
      } catch {
        get().setServerReachable(false);
      } finally {
        set({ lastCheckedAt: Date.now() });
        inflight = null;
      }
      return get().status;
    })();
    return inflight;
  },
}));

const HEARTBEAT_MS = 15_000;

/** Wires browser events, the 15s /health heartbeat and request failures. Returns a teardown. */
export function startConnectivity(): () => void {
  const c = useConnectivity.getState();
  const onOnline = () => {
    useConnectivity.getState().setBrowserOnline(true);
    void useConnectivity.getState().check();
  };
  const onOffline = () => useConnectivity.getState().setBrowserOnline(false);
  window.addEventListener("online", onOnline);
  window.addEventListener("offline", onOffline);
  const stopNet = onNetworkResult((ok) => {
    const s = useConnectivity.getState();
    if (ok && !s.serverReachable) s.setServerReachable(true);
    if (!ok && s.serverReachable) void s.check(); // check immediately on a failed request
  });
  void c.check();
  const timer = window.setInterval(() => {
    if (useConnectivity.getState().browserOnline) void useConnectivity.getState().check();
  }, HEARTBEAT_MS);
  return () => {
    window.removeEventListener("online", onOnline);
    window.removeEventListener("offline", onOffline);
    stopNet();
    window.clearInterval(timer);
  };
}

/** Resolve when the app is online again (used by upload queue and polling). */
export function onceOnline(cb: () => void): () => void {
  if (useConnectivity.getState().status === "online") {
    cb();
    return () => undefined;
  }
  return useConnectivity.subscribe((s, prev) => {
    if (s.status === "online" && prev.status !== "online") cb();
  });
}
