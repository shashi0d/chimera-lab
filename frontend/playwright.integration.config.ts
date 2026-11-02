import { defineConfig, devices } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

// R1 lead: the built UI (frontend/dist) served by the real backend in mock mode, one origin, no Vite.
// Build first: `npx vite build`. Run: `npx playwright test -c playwright.integration.config.ts`.
const PORT = 8300;
const PY = process.env.PYTHON ?? "../.venv/bin/python";

export default defineConfig({
  testDir: "tests/integration",
  timeout: 90_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: { ...devices["Desktop Chrome"], baseURL: `http://localhost:${PORT}`, viewport: { width: 1440, height: 900 }, trace: "retain-on-failure" },
  webServer: {
    command: `${PY} -m uvicorn app.main:app --port ${PORT} --workers 1`,
    cwd: "../backend",
    url: `http://localhost:${PORT}/health`,
    reuseExistingServer: false,
    timeout: 60_000,
    env: {
      CHIMERA_MODE: "mock",
      META_API_KEY: "",
      BASETEN_API_KEY_MODEL_MUSE_SPARK_OPEN_26: "",
      LOCAL_DATA_DIR: join(tmpdir(), `chimera-r1-int-${Date.now()}`),
      EVO_VISITOR_DAILY_RUNS: "1000",
      EVO_DAILY_RUNS: "1000",
      EVO_RUNS_PER_MINUTE_PER_IP: "1000",
    },
  },
});
