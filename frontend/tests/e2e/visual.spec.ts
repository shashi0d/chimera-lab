import { expect, test, type Page } from "@playwright/test";
import { addImages, fuse, openApp, waitForResult } from "./helpers";

// PV-05 baselines: approved screens that F-rounds must not silently break.
// Timers and blob previews vary run to run, so they are masked.
const masks = (page: Page) => [page.locator(".node__timer"), page.locator(".step__time"), page.locator(".topbar__save")];

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
      await addImages(page, ["lion", "tiger"]);
      await fuse(page);
      await waitForResult(page);
      await page.getByRole("button", { name: "Fit to view" }).click();
      await page.getByRole("button", { name: "How this was made" }).click();
      await settle(page);
      await expect(page).toHaveScreenshot(`result-panel-${theme}.png`, { mask: masks(page) });
    });
  });
}
