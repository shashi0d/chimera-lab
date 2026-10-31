import { expect, test } from "@playwright/test";
import { addImages, fuse, openApp, openSection, waitForResult } from "./helpers";

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
  await page.getByRole("radio", { name: "Version 1 of 2" }).click();
  await expect(page.locator(".node--result .node__kicker")).toContainText("v1");

  await page.getByRole("button", { name: "How this was made" }).click();
  const panel = page.getByRole("complementary");
  // U1: the drawer leads with a plain summary and stat cards; evidence sits in sections
  await expect(panel.locator(".panel__summary")).toContainText("Real hybrids of these parents exist");
  await expect(panel.locator(".stat")).toHaveCount(5);
  await openSection(page, "Parents as read");
  await expect(panel.getByText("Panthera leo")).toBeVisible();
  await openSection(page, "Prompt and sources");
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
  await openSection(page, "Rules and warnings");
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

test("F1 anatomy: pin parts, fuse, panel credits you", async ({ page }) => {
  await openApp(page);
  await addImages(page, ["common_octopus", "scarlet_macaw"]);
  await page.getByRole("button", { name: "Head from Auto (model decides)" }).click(); // → A
  await page.getByRole("button", { name: "Head from A" }).click(); // → B
  await page.getByRole("button", { name: "Covering from Auto (model decides)" }).click(); // → A
  await fuse(page);
  await waitForResult(page);
  await page.getByRole("button", { name: "How this was made" }).click();
  const head = page.locator(".donor").filter({ hasText: "Head" });
  await expect(head).toContainText("B");
  await expect(head).toContainText("you");
  await expect(page.locator(".donor").filter({ hasText: "Body" })).toContainText("model");
  await page.keyboard.press("Escape");
  // changing a pin outdates the result
  await page.getByRole("button", { name: "Tail from Auto (model decides)" }).click();
  await expect(page.locator(".node--result .node__status")).toHaveText(/Outdated/);
});

test("F2 field card: make, write, download PNG, out of date after v2", async ({ page }) => {
  await openApp(page);
  await addImages(page, ["lion", "tiger"]);
  await fuse(page);
  await waitForResult(page);
  await page.locator(".node--result").hover();
  await page.getByRole("button", { name: "Make field card" }).click();
  await page.getByRole("button", { name: "Write card" }).click();
  const card = page.locator(".node--field-card");
  await expect(card.locator(".field-card__binomial")).toContainText("Panthera", { timeout: 20_000 });
  await expect(card).toContainText("Lion 126-272 kg");
  await expect(card).toContainText("Generated fusion. Not a real animal.");
  const download = page.waitForEvent("download");
  await card.getByRole("button", { name: "Download PNG" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/-field-card\.png$/);
  const path = await file.path();
  const { readFileSync } = await import("node:fs");
  const bytes = readFileSync(path);
  expect(bytes.subarray(1, 4).toString()).toBe("PNG");
  expect(bytes.readUInt32BE(16)).toBe(1600); // width from the IHDR chunk
  await page.getByRole("button", { name: "Fuse again" }).click();
  await waitForResult(page, 2);
  await expect(card).toContainText("Written for v1; the Result now shows v2.");
  await card.getByRole("button", { name: "Rewrite for v2" }).click();
  await expect(card).not.toContainText("Written for v1", { timeout: 20_000 });
});
