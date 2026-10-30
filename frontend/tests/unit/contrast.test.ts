import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const css = readFileSync(resolve(__dirname, "../../src/styles/theme.css"), "utf8");

function block(selector: string): Record<string, string> {
  const start = css.indexOf(`${selector} {`);
  const body = css.slice(start, css.indexOf("\n}", start));
  return Object.fromEntries([...body.matchAll(/--([\w-]+):\s*(#[0-9A-Fa-f]{6})/g)].map((m) => [m[1] as string, m[2] as string]));
}

function lum(hex: string): number {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * (c[0] as number) + 0.7152 * (c[1] as number) + 0.0722 * (c[2] as number);
}
const ratio = (a: string, b: string) => {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p) as [number, number];
  return (x + 0.05) / (y + 0.05);
};

const light = block(":root");
const dark = { ...light, ...block(':root[data-theme="dark"]') };

// [foreground, background, minimum] - text pairs need 4.5, essential UI 3.0
const PAIRS: Array<[string, string, number]> = [
  ["ink", "vellum", 4.5],
  ["ink", "folio", 4.5],
  ["ink-2", "folio", 4.5],
  ["ink-2", "vellum", 4.5],
  ["ink-3", "folio", 4.5],
  ["ink-3", "vellum", 4.5],
  ["ink-2", "lapis-soft", 4.5],
  ["ink-2", "ochre-soft", 4.5],
  ["ink-2", "cinnabar-soft", 4.5],
  ["on-moss", "moss", 4.5],
  ["moss", "folio", 4.5],
  ["lapis", "folio", 4.5],
  ["lapis", "lapis-soft", 4.5],
  ["ochre-ink", "folio", 4.5],
  ["ochre-ink", "ochre-soft", 4.5],
  ["cinnabar", "folio", 4.5],
  ["ink", "cinnabar-soft", 4.5],
  ["vellum", "ink", 4.5],
];

describe.each([
  ["light", light],
  ["dark", dark],
])("WCAG AA contrast, %s theme (DESIGN.md)", (_name, t) => {
  it.each(PAIRS)("%s on %s ≥ %s", (fg, bg, min) => {
    expect(t[fg], fg).toBeDefined();
    expect(t[bg], bg).toBeDefined();
    expect(ratio(t[fg] as string, t[bg] as string)).toBeGreaterThanOrEqual(min);
  });
});
