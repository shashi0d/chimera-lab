import { defineConfig, devices } from "@playwright/test";

// R1: the e2e suite runs the app in test mode against the fixture-backed mock transport (src/evo/mock.ts,
// docs/api_fixtures/), so no backend is started and no model is called. Port 8100 stays reserved for a backend.
const WEB_PORT = 5174;

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 60_000,
  expect: { timeout: 15_000, toHaveScreenshot: { maxDiffPixelRatio: 0.01, animations: "disabled" } },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  snapshotPathTemplate: "tests/visual/baselines/{testFilePath}/{arg}{ext}",
  use: {
    ...devices["Desktop Chrome"],
    baseURL: `http://localhost:${WEB_PORT}`,
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `npx vite --mode test --port ${WEB_PORT} --strictPort`,
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: false,
      env: { VITE_EVO_TRANSPORT: "mock" },
    },
  ],
});
