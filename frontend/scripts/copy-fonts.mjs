// Copies the self-hosted ZD fonts (all SIL OFL 1.1) from @fontsource into public/fonts (committed).
import { copyFileSync, mkdirSync, readdirSync, rmSync } from "node:fs";
const files = [
  ["space-grotesk", "space-grotesk-latin-500-normal.woff2"],
  ["space-grotesk", "space-grotesk-latin-600-normal.woff2"],
  ["hanken-grotesk", "hanken-grotesk-latin-400-normal.woff2"],
  ["hanken-grotesk", "hanken-grotesk-latin-500-normal.woff2"],
  ["hanken-grotesk", "hanken-grotesk-latin-600-normal.woff2"],
  ["jetbrains-mono", "jetbrains-mono-latin-400-normal.woff2"],
  ["jetbrains-mono", "jetbrains-mono-latin-500-normal.woff2"],
];
mkdirSync("public/fonts", { recursive: true });
for (const f of readdirSync("public/fonts")) rmSync(`public/fonts/${f}`); // U1: the field-paper fonts are retired
for (const [pkg, file] of files) copyFileSync(`node_modules/@fontsource/${pkg}/files/${file}`, `public/fonts/${file}`);
for (const pkg of ["space-grotesk", "hanken-grotesk", "jetbrains-mono"]) copyFileSync(`node_modules/@fontsource/${pkg}/LICENSE`, `public/fonts/LICENSE-${pkg}.txt`);
console.log(`copied ${files.length} font files`);
