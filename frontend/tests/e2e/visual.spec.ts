import { expect, test, type Page } from "@playwright/test";
import { seedLive } from "../visual/liveSeed";
import { openApp } from "./helpers";

const API = "http://localhost:8100"; // playwright.config.ts API_PORT

// PV-05 baselines: approved screens that F-rounds must not silently break.
// The live timer and save state vary run to run, so they are masked; seeded live runs are fixed.
const masks = (page: Page) => [page.locator(".node__timer"), page.locator(".topbar__save")];

/** U1: baselines use real generated images, never mock drawings (tests/visual/liveSeed.ts). */
async function addLive(page: Page, files: string[]) {
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Add images" }).click();
  await (await chooser).setFiles(files);
  await expect(page.locator(".node--image-input .status--ok")).toHaveCount(2, { timeout: 20_000 });
}

async function settle(page: Page) {
  await page.evaluate(() => window.__chimera.clearToasts());
  await page.mouse.move(5, 895);
  await page.waitForTimeout(300);
}

for (const theme of ["light", "dark"] as const) {
  test.describe(`baselines ${theme}`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript((t) => localStorage.setItem("chimera.theme", t), theme);
    });

    test("empty canvas", async ({ page }) => {
      await openApp(page);
      await settle(page);
      await expect(page).toHaveScreenshot(`empty-${theme}.png`, { mask: masks(page) });
    });

    test("result with panel", async ({ page }) => {
      await openApp(page);
      await seedLive(page, ["lion_tiger"], { api: API, addInputs: (files) => addLive(page, files) });
      await page.getByRole("button", { name: "Fit to view" }).click();
      await page.getByRole("button", { name: "How this was made" }).click();
      await settle(page);
      await expect(page).toHaveScreenshot(`result-panel-${theme}.png`, { mask: masks(page) });
    });
  });
}
