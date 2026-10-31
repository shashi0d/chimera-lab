import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { PNG_FONTS, PNG_TOKENS } from "../../src/nodes/field-card/renderPng";

// U1 regression: the exported field-card PNG reads theme tokens and fonts by name. When the
// identity changed, the old names silently resolved to nothing and the PNG lost all its text.

const css = readFileSync(resolve(__dirname, "../../src/styles/theme.css"), "utf8");

describe("field-card PNG paints with tokens and fonts that exist", () => {
  it.each(PNG_TOKENS)("%s is defined in theme.css", (t) => {
    expect(css).toMatch(new RegExp(`^\\s*${t}:`, "m"));
  });

  it.each(PNG_FONTS)("%s is a self-hosted @font-face", (f) => {
    const family = f.match(/'([^']+)'/)?.[1];
    expect(css).toContain(`font-family: "${family}"`);
  });
});
