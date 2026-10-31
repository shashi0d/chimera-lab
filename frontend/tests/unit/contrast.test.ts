import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// U1: contrast is measured on the ZD tokens as theme.css actually defines them (ZD.md §3).
// var() chains are resolved, translucent tints are composited onto the card, color-mix is mixed.

const css = readFileSync(resolve(__dirname, "../../src/styles/theme.css"), "utf8");
const zd = readFileSync(resolve(__dirname, "../../../docs/design-system/zd-tokens.css"), "utf8");

type Vars = Record<string, string>;

function blocks(opener: RegExp): Vars {
  const out: Vars = {};
  const lines = css.split("\n");
  let on = false;
  for (const line of lines) {
    if (!on && opener.test(line)) on = true;
    else if (on && /^\}/.test(line)) on = false;
    else if (on) for (const m of line.matchAll(/--([\w-]+):\s*([^;]+);/g)) out[m[1] as string] = (m[2] as string).replace(/\/\*.*\*\//, "").trim();
  }
  return out;
}

const light = blocks(/^:root \{/);
const dark = {
  ...light,
  ...blocks(/^\[data-theme="dark"\] \{/),
  ...blocks(/^:root\[data-theme="dark"\] \{/),
};

type RGBA = [number, number, number, number];

function resolveVar(v: Vars, value: string, depth = 0): string {
  if (depth > 12) throw new Error(`var loop: ${value}`);
  return value.replace(/var\(--([\w-]+)\)/g, (_, name: string) => {
    const raw = v[name];
    if (raw === undefined) throw new Error(`undefined token --${name}`);
    return resolveVar(v, raw, depth + 1);
  });
}

function parse(v: Vars, value: string): RGBA {
  const s = resolveVar(v, value).trim();
  let m = s.match(/^#([0-9a-f]{6})$/i);
  if (m) {
    const h = m[1] as string;
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16), 1];
  }
  m = s.match(/^rgba?\(([^)]+)\)$/);
  if (m) {
    const p = (m[1] as string).split(",").map((x) => parseFloat(x));
    return [p[0] as number, p[1] as number, p[2] as number, p[3] ?? 1];
  }
  m = s.match(/^color-mix\(in srgb,\s*(.+?)\s+(\d+)%,\s*(.+)\)$/);
  if (m) {
    const a = parse(v, m[1] as string);
    const b = parse(v, m[3] as string);
    const w = Number(m[2]) / 100;
    return [0, 1, 2].map((i) => (a[i] as number) * w + (b[i] as number) * (1 - w)).concat(1) as RGBA;
  }
  throw new Error(`cannot parse colour: ${s}`);
}

/** Composite fg over an opaque bg. */
function over(fg: RGBA, bg: RGBA): RGBA {
  const a = fg[3];
  return [0, 1, 2].map((i) => (fg[i] as number) * a + (bg[i] as number) * (1 - a)).concat(1) as RGBA;
}

function lum(c: RGBA): number {
  const [r, g, b] = c
    .slice(0, 3)
    .map((x) => x / 255)
    .map((x) => (x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4)) as [number, number, number];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function ratio(a: RGBA, b: RGBA): number {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p) as [number, number];
  return (x + 0.05) / (y + 0.05);
}

/** Darkest stop of --ground-app: the worst case for text on the ground (ZD.md §3). */
function groundDarkest(v: Vars): RGBA {
  const stops = [...resolveVar(v, "var(--ground-app)").matchAll(/#[0-9a-f]{6}/gi)].map((m) => parse(v, m[0]));
  return stops.sort((a, b) => lum(a) - lum(b))[0] as RGBA;
}

/** A surface name, or "tint over surface" ("tint-danger/surface-card"). */
function surface(v: Vars, name: string): RGBA {
  if (name === "ground") return groundDarkest(v);
  const [top, base] = name.split("/");
  const baseRgba = base ? surface(v, base) : null;
  const c = parse(v, `var(--${top})`);
  return baseRgba ? over(c, baseRgba) : c;
}

// [foreground token, background, minimum]. Text pairs need 4.5.
const PAIRS: Array<[string, string, number]> = [
  ["text-strong", "surface-card", 4.5],
  ["text-body", "surface-card", 4.5],
  ["text-muted", "surface-card", 4.5], // kickers and meta on cards
  ["text-muted", "surface-modal", 4.5], // drawer
  ["text-strong", "ground", 4.5],
  ["text-body", "ground", 4.5], // anything read on the ground (save state, zoom value)
  ["accent-text", "surface-card", 4.5],
  ["accent-text", "tint-indigo/surface-card", 4.5], // "Generated fusion", running status
  ["info-text", "tint-info/surface-card", 4.5], // real-hybrid pill
  ["warning-text", "surface-card", 4.5],
  ["warning-text", "tint-warning/surface-card", 4.5], // warnings, "Unverified"
  ["success-text-aa", "surface-card", 4.5],
  ["success-text-aa", "tint-success/surface-card", 4.5], // done status
  ["danger-text-aa", "surface-card", 4.5],
  ["danger-text-aa", "tint-danger/surface-card", 4.5], // error status
  ["text-strong", "tint-warning/surface-card", 4.5],
  ["text-strong", "tint-danger/surface-card", 4.5],
  ["white", "indigo-600", 4.5], // Fuse and every primary button
  ["toast-text-aa", "toast-bg-aa", 4.5], // toasts, tooltips, offline banner
  ["text-strong", "donor-a-fill", 4.5], // pinned body regions
  ["text-strong", "donor-b-fill", 4.5],
  ["text-body", "surface-card", 4.5],
];

// Non-text UI parts need 3:1 against the card (WCAG 1.4.11).
const UI_PAIRS: Array<[string, string, number]> = [
  ["accent", "surface-card", 3], // focus outline, selected border
  ["info", "surface-card", 3], // image port
  ["donor-a", "surface-card", 3],
  ["donor-b", "surface-card", 3],
];

describe.each([
  ["light", light],
  ["dark", dark],
])("WCAG AA contrast, %s theme (ZD.md §3)", (_name, v) => {
  it.each([...PAIRS, ...UI_PAIRS])("%s on %s ≥ %s", (fg, bg, min) => {
    expect(ratio(surface(v, fg), surface(v, bg))).toBeGreaterThanOrEqual(min);
  });
});

describe("ZD tokens are used as shipped", () => {
  it("theme.css contains zd-tokens.css verbatim", () => {
    expect(css.includes(zd)).toBe(true);
  });

  it("the -aa deviations are needed: ZD's own values miss 4.5:1 in light", () => {
    expect(ratio(surface(light, "success-text"), surface(light, "surface-card"))).toBeLessThan(4.5);
    expect(ratio(surface(light, "danger-text"), surface(light, "tint-danger/surface-card"))).toBeLessThan(4.5);
    expect(ratio(surface(dark, "white"), surface(dark, "ink-900"))).toBeLessThan(4.5);
  });

  it("dark keeps ZD's text values", () => {
    expect(resolveVar(dark, "var(--success-text-aa)")).toBe(resolveVar(dark, "var(--success-text)"));
    expect(resolveVar(dark, "var(--danger-text-aa)")).toBe(resolveVar(dark, "var(--danger-text)"));
  });

  it("every -aa token is defined in both themes", () => {
    const aa = Object.keys(light).filter((k) => k.endsWith("-aa"));
    expect(aa.sort()).toEqual(["danger-text-aa", "success-text-aa", "toast-bg-aa", "toast-text-aa"]);
    for (const k of aa) expect(dark[k], k).toBeDefined();
  });

  it("the gradient is used on the brand mark only", () => {
    const uses = [...css.matchAll(/^\s*background:\s*var\(--gradient-[\w-]+\)/gm)];
    expect(uses).toHaveLength(1);
    expect(css).toMatch(/\.brand__mark \{[^}]*background: var\(--gradient-mark\)/);
  });
});
