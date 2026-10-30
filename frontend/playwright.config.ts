import { defineConfig, devices } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

const API_PORT = 8100;
const WEB_PORT = 5174;
const PY = process.env.PYTHON ?? "../.venv/bin/python";

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
      command: `${PY} -m uvicorn app.main:app --port ${API_PORT}`,
      cwd: "../backend",
      url: `http://localhost:${API_PORT}/health`,
      reuseExistingServer: false,
      env: {
        CHIMERA_MODE: "mock",
        MOCK_DELAY_SCALE: "0.1",
        RETRY_BASE_SECONDS: "0.01",
        RUNS_PER_MINUTE_PER_SESSION: "1000",
        DATA_PATH: "backend/tests/fixtures/chimera_data.sample.json",
        LOCAL_DATA_DIR: join(tmpdir(), `chimera-e2e-${Date.now()}`),
        CORS_ORIGINS: `http://localhost:${WEB_PORT}`,
      },
    },
    {
      command: `npx vite --mode test --port ${WEB_PORT} --strictPort`,
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: false,
      env: { VITE_API_BASE_URL: `http://localhost:${API_PORT}` },
    },
  ],
});
