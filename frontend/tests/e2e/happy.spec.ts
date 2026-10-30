import { expect, test } from "@playwright/test";
import { addImages, fuse, openApp, waitForResult } from "./helpers";

test("two images to a fusion, re-run keeps versions, How this was made", async ({ page }) => {
  await openApp(page);
  await expect(page.getByRole("heading", { name: "Start with two animals" })).toBeVisible();
  await addImages(page, ["lion", "tiger"]);
  await expect(page.locator(".react-flow__edge")).toHaveCount(2);
  await fuse(page);
  await expect(page.locator(".node--fusion .steps")).toBeVisible();
  await waitForResult(page);
  await expect(page.getByText("Generated fusion").first()).toBeVisible();
  await expect(page.locator(".badge--hybrid")).toHaveText(/Real hybrid exists: Liger/);

  await page.getByRole("button", { name: "Fuse again" }).click();
  await waitForResult(page, 2);
  await page.getByRole("button", { name: "Previous version" }).click();
  await expect(page.locator(".version-switch__label")).toContainText("v1");

  await page.getByRole("button", { name: "How this was made" }).click();
  const panel = page.getByRole("complementary");
  await expect(panel.getByText("Parents as read")).toBeVisible();
  await expect(panel.getByText("Panthera leo")).toBeVisible();
  await expect(panel.getByText("Reference image 1 shows a lion", { exact: false })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(panel).toBeHidden();
});

test("warnings path: octopus + macaw shows field notes, image still shown", async ({ page }) => {
  await openApp(page);
  await addImages(page, ["common_octopus", "scarlet_macaw"]);
  await fuse(page);
  await waitForResult(page);
  await expect(page.locator(".badge--warn")).toBeVisible();
  await page.getByRole("button", { name: "How this was made" }).click();
  await expect(page.getByText("R-A2-01")).toBeVisible();
});

test("canvas survives reload; undo/redo work", async ({ page }) => {
  await openApp(page);
  await addImages(page, ["lion", "tiger"]);
  await page.locator(".node--image-input").first().click();
  await page.keyboard.press("Delete");
  await expect(page.locator(".node--image-input")).toHaveCount(1);
  await page.keyboard.press("Control+z");
  await expect(page.locator(".node--image-input")).toHaveCount(2);
  await page.keyboard.press("Control+Shift+z");
  await expect(page.locator(".node--image-input")).toHaveCount(1);
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(800); // autosave debounce
  await page.reload();
  await expect(page.locator(".node--image-input")).toHaveCount(2);
  await expect(page.locator(".react-flow__edge")).toHaveCount(2);
});

test("refused connection: wrong port type shakes and explains", async ({ page }) => {
  await openApp(page);
  await addImages(page, ["lion", "tiger"]);
  await fuse(page);
  await waitForResult(page);
  const from = page.locator(".node--image-input .port--out").first();
  const to = page.locator(".node--result .port--in");
  await from.dragTo(to);
  await expect(page.getByText(/Those ports don't fit/)).toBeVisible();
});
