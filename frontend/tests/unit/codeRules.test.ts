import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = resolve(__dirname, "../../src");

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? files(p) : /\.(ts|tsx)$/.test(f) ? [p] : [];
  });
}

describe("code rules (TASKSHEET Section 9)", () => {
  it.each(["nodes", "graph", "runs", "api"])("no TypeScript any in src/%s", (dir) => {
    const offenders = files(join(SRC, dir)).filter((f) => /(:\s*any\b|as any\b|<any>|any\[\])/.test(readFileSync(f, "utf8")));
    expect(offenders).toEqual([]);
  });

  it("frontend source never references backend secrets", () => {
    const offenders = files(SRC).filter((f) => /META_API_KEY|SUPABASE_SERVICE_KEY|MODAL_TOKEN|service_role/.test(readFileSync(f, "utf8")));
    expect(offenders).toEqual([]);
  });
});
