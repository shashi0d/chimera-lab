import { beforeEach, describe, expect, it, vi } from "vitest";
import { httpTransport } from "../../src/evo/http";
import { useConnectivity } from "../../src/connectivity/store";

beforeEach(() => useConnectivity.setState({ browserOnline: true, serverReachable: true, forced: null, status: "online", mode: null }));

describe("connectivity (TASKSHEET 7.7)", () => {
  it("offline when the browser says so", () => {
    useConnectivity.getState().setBrowserOnline(false);
    expect(useConnectivity.getState().status).toBe("offline");
  });
  it("server unreachable is distinct from offline", async () => {
    vi.spyOn(httpTransport, "health").mockRejectedValue(new Error("down"));
    expect(await useConnectivity.getState().check()).toBe("unreachable");
  });
  it("health check restores online and records the mode", async () => {
    useConnectivity.getState().setServerReachable(false);
    vi.spyOn(httpTransport, "health").mockResolvedValue({ mode: "mock" });
    expect(await useConnectivity.getState().check()).toBe("online");
    expect(useConnectivity.getState().mode).toBe("mock");
  });
  it("forced status wins (test hook)", () => {
    useConnectivity.getState().force("offline");
    expect(useConnectivity.getState().status).toBe("offline");
    useConnectivity.getState().force(null);
    expect(useConnectivity.getState().status).toBe("online");
  });
});
