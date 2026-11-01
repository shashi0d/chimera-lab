/// <reference types="vitest/config" />
import { createReadStream, existsSync, statSync } from "node:fs";
import { dirname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

const FIXTURES = resolve(dirname(fileURLToPath(import.meta.url)), "../docs/api_fixtures");

/**
 * Dev and test only: serves the contract fixture images at /__fixtures/images/... for the mock transport
 * (src/evo/mock.ts). Nothing is copied into the production bundle; `vite build` never runs this.
 */
function fixtureImages(): Plugin {
  return {
    name: "chimera-fixture-images",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use("/__fixtures/", (req, res, next) => {
        const path = resolve(FIXTURES, decodeURIComponent((req.url ?? "").split("?")[0]!.replace(/^\/+/, "")));
        if (!path.startsWith(FIXTURES + sep) || !/\.(jpe?g|png|webp)$/i.test(path) || !existsSync(path) || !statSync(path).isFile()) return next();
        res.setHeader("Content-Type", /\.png$/i.test(path) ? "image/png" : /\.webp$/i.test(path) ? "image/webp" : "image/jpeg");
        res.setHeader("Cache-Control", "public, max-age=3600");
        createReadStream(path).pipe(res);
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), fixtureImages()],
  server: { port: 5173, strictPort: true, fs: { allow: [".", FIXTURES] } },
  preview: { port: 4173, strictPort: true },
  build: { sourcemap: false, chunkSizeWarningLimit: 900 },
  test: {
    environment: "jsdom",
    setupFiles: ["tests/setup.ts"],
    include: ["tests/unit/**/*.test.{ts,tsx}", "tests/component/**/*.test.{ts,tsx}"],
    css: false,
    restoreMocks: true,
  },
});
