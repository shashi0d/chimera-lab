import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../src/api/client";
import { ApiRequestError } from "../../src/api/errors";
import { useConnectivity } from "../../src/connectivity/store";
import { POLL, pollingTransport } from "../../src/runs/transport";
import type { Run } from "../../src/types/api";

const run = (status: Run["status"], version: number): Run => ({
  id: "run1", graphId: "g", nodeId: "f", sessionId: null, status, steps: [], result: null, error: null,
  failedInput: null, createdAt: "", updatedAt: "", version, usage: {},
});

beforeEach(() => {
  vi.useFakeTimers();
  useConnectivity.setState({ browserOnline: true, serverReachable: true, forced: null, status: "online" });
});
afterEach(() => vi.useRealTimers());

describe("polling transport (TASKSHEET 4.4)", () => {
  it("polls with ETag until terminal", async () => {
    const seq = [
      { run: run("running", 1), etag: '"1"' },
      { run: null, etag: '"1"' },
      { run: run("succeeded", 2), etag: '"2"' },
    ];
    const spy = vi.spyOn(api, "getRun").mockImplementation(async () => seq.shift() as never);
    const updates: string[] = [];
    pollingTransport.watch("run1", (r) => updates.push(r.status), () => undefined);
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(POLL.fastMs);
    await vi.advanceTimersByTimeAsync(POLL.fastMs);
    await vi.advanceTimersByTimeAsync(POLL.fastMs * 3);
    expect(updates).toEqual(["running", "succeeded"]);
    expect(spy).toHaveBeenCalledTimes(3);
    expect(spy.mock.calls[1]).toEqual(["run1", '"1"']);
  });

  it("backs off to 5s after 60s", async () => {
    const spy = vi.spyOn(api, "getRun").mockResolvedValue({ run: null, etag: '"x"' });
    pollingTransport.watch("run1", () => undefined, () => undefined);
    await vi.advanceTimersByTimeAsync(61_000);
    const before = spy.mock.calls.length;
    await vi.advanceTimersByTimeAsync(POLL.slowMs);
    expect(spy.mock.calls.length - before).toBe(1);
  });

  it("pauses while offline and resumes on reconnect (7.7)", async () => {
    const spy = vi.spyOn(api, "getRun").mockResolvedValue({ run: run("succeeded", 3), etag: null });
    useConnectivity.getState().setBrowserOnline(false);
    const updates: string[] = [];
    pollingTransport.watch("run1", (r) => updates.push(r.status), () => undefined);
    await vi.advanceTimersByTimeAsync(10_000);
    expect(spy).not.toHaveBeenCalled();
    useConnectivity.getState().setBrowserOnline(true);
    await vi.advanceTimersByTimeAsync(0);
    expect(updates).toEqual(["succeeded"]);
  });

  it("waits for the connection after a network error", async () => {
    const spy = vi
      .spyOn(api, "getRun")
      .mockRejectedValueOnce(new ApiRequestError({ code: "NETWORK", message: "x", retryable: true }))
      .mockResolvedValue({ run: run("failed", 2), etag: null });
    const updates: string[] = [];
    pollingTransport.watch("run1", (r) => updates.push(r.status), () => undefined);
    await vi.advanceTimersByTimeAsync(0);
    expect(updates).toEqual([]);
    useConnectivity.getState().setServerReachable(false);
    useConnectivity.getState().setServerReachable(true);
    await vi.advanceTimersByTimeAsync(0);
    expect(updates).toEqual(["failed"]);
    expect(spy).toHaveBeenCalledTimes(2);
  });

  it("stop() halts polling", async () => {
    const spy = vi.spyOn(api, "getRun").mockResolvedValue({ run: run("running", 1), etag: null });
    const sub = pollingTransport.watch("run1", () => undefined, () => undefined);
    await vi.advanceTimersByTimeAsync(0);
    sub.stop();
    await vi.advanceTimersByTimeAsync(10_000);
    expect(spy).toHaveBeenCalledTimes(1);
  });
});
