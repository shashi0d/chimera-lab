import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// U1-10: no UI text under 12px. The only exception is the ZD mono kicker (10px uppercase,
// letter-spaced), which sits in --text-muted on cards (or --text-body on the header ground).

const css = readFileSync(resolve(__dirname, "../../src/styles/theme.css"), "utf8");
const ours = css.slice(css.indexOf("/* <<< zd-tokens.css end */"));
const rules = [...ours.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((m) => ({ selector: (m[1] as string).trim().split("\n").pop()!.trim(), body: m[2] as string }));

describe("12px text floor (U1-10)", () => {
  it("never uses ZD's sub-12px type tokens", () => {
    for (const t of ["--type-meta-sm", "--type-count", "--type-label", "--type-nav-kicker"]) expect(ours, t).not.toContain(`var(${t})`);
  });

  it("explicit font sizes are 12px or more (React Flow's hidden attribution aside)", () => {
    for (const r of rules) {
      for (const m of r.body.matchAll(/font-size:\s*([\d.]+)px/g)) {
        if (r.selector.includes("react-flow__attribution")) continue;
        expect(Number(m[1]), r.selector).toBeGreaterThanOrEqual(12);
      }
    }
  });

  it("the 10px kicker is only used for kickers, in muted text (or raised to 12px)", () => {
    for (const r of rules.filter((x) => x.body.includes("var(--type-kicker)"))) {
      const raised = /font-size:\s*1[2-9]px/.test(r.body);
      if (raised) continue;
      expect(r.selector, r.selector).toMatch(/kicker/);
      expect(r.body).toMatch(/text-transform:\s*uppercase/);
      expect(r.body).toMatch(/color:\s*var\(--text-(muted|body)\)/);
    }
  });
});
