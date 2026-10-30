import { describe, expect, it } from "vitest";
import { errorMessages, presentError } from "../../src/api/errorMessages";
import { ApiRequestError, toAppError } from "../../src/api/errors";
import api from "../../src/types/api.ts?raw";

describe("error message map (TASKSHEET 7.5)", () => {
  it("has a message for every server error code", () => {
    const block = api.slice(api.indexOf("export type ErrorCode"), api.indexOf(";", api.indexOf("export type ErrorCode")));
    const codes = [...block.matchAll(/"([A-Z_]+)"/g)].map((m) => m[1] as keyof typeof errorMessages);
    expect(codes.length).toBeGreaterThanOrEqual(17);
    for (const c of codes) expect(errorMessages[c]?.title, c).toBeTruthy();
  });

  it("retryable codes get a retry action, others say what to change", () => {
    expect(presentError({ code: "UPSTREAM_ERROR", message: "x", retryable: true }).retry).toBe(true);
    const refused = presentError({ code: "MODEL_REFUSED", message: "x", retryable: false });
    expect(refused.retry).toBe(false);
    expect(refused.fix).toBeTruthy();
  });

  it("BUDGET_EXCEEDED never offers retry", () => {
    expect(presentError({ code: "BUDGET_EXCEEDED", message: "x", retryable: true }).retry).toBe(false);
  });

  it("never echoes server text and exposes an id for unknown errors", () => {
    const p = presentError({ code: "INTERNAL", message: "Traceback: secret", retryable: true, errorId: "abc123" });
    expect(JSON.stringify(p)).not.toContain("Traceback");
    expect(p.errorId).toBe("abc123");
    const unknown = toAppError(new Error("boom"));
    expect(unknown.code).toBe("UNKNOWN");
    expect(presentError(unknown).errorId).toBeTruthy();
  });

  it("round-trips ApiRequestError", () => {
    const e = new ApiRequestError({ code: "RATE_LIMITED", message: "slow", retryable: true, retryAfterMs: 4000 }, 429);
    expect(toAppError(e)).toMatchObject({ code: "RATE_LIMITED", retryAfterMs: 4000 });
  });
});
