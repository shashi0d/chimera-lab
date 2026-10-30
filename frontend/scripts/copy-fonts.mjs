// Copies the self-hosted font files from @fontsource into public/fonts (committed).
import { copyFileSync, mkdirSync } from "node:fs";
const files = [
  ["newsreader", "newsreader-latin-400-normal.woff2"],
  ["newsreader", "newsreader-latin-400-italic.woff2"],
  ["newsreader", "newsreader-latin-500-normal.woff2"],
  ["newsreader", "newsreader-latin-600-normal.woff2"],
  ["ibm-plex-sans", "ibm-plex-sans-latin-400-normal.woff2"],
  ["ibm-plex-sans", "ibm-plex-sans-latin-500-normal.woff2"],
  ["ibm-plex-sans", "ibm-plex-sans-latin-600-normal.woff2"],
  ["ibm-plex-mono", "ibm-plex-mono-latin-400-normal.woff2"],
  ["ibm-plex-mono", "ibm-plex-mono-latin-500-normal.woff2"],
];
mkdirSync("public/fonts", { recursive: true });
for (const [pkg, file] of files) copyFileSync(`node_modules/@fontsource/${pkg}/files/${file}`, `public/fonts/${file}`);
console.log(`copied ${files.length} font files`);
