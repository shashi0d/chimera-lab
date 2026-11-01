import { expect, test } from "@playwright/test";
import { addPhotos, fx, make, openLab, typeNames } from "./helpers";

test("offline: banner, Make creature disabled with the reason; back online re-enables it", async ({ page, context }) => {
  await openLab(page);
  await typeNames(page, "lion", "tiger");
  await context.setOffline(true);
  await expect(page.locator(".banner--offline")).toBeVisible();
  await expect(page.locator(".fusion-node__make")).toBeDisabled();
  await expect(page.locator(".node--fusion")).toContainText("You're offline. Making a creature needs a connection.");
  await context.setOffline(false);
  await expect(page.locator(".banner--offline")).toHaveCount(0);
  await expect(page.locator(".fusion-node__make")).toBeEnabled();
});

test("server unreachable shows a distinct banner", async ({ page }) => {
  await openLab(page);
  await page.evaluate(() => window.__chimera.force("unreachable"));
  await expect(page.locator(".banner--unreachable")).toBeVisible();
  await expect(page.locator(".banner--offline")).toHaveCount(0);
});

test("corrupt autosave: discarded with a toast, app starts clean", async ({ page }) => {
  await openLab(page);
  await page.evaluate(() => window.__chimera.writeAutosave("garbage{"));
  await page.reload();
  await expect(page.getByText(/couldn't be read/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Start with two animals" })).toBeVisible();
});

test("broken saved graph: unknown node placeholder (e.g. a v1 field card), orphan edges removed", async ({ page }) => {
  await openLab(page);
  await page.evaluate(() =>
    window.__chimera.writeAutosave({
      schemaVersion: 1,
      graphId: "broken",
      nodes: [
        { id: "s1", type: "field-card", version: 1, position: { x: 0, y: 0 }, config: {}, data: {} },
        { id: "f1", type: "fusion", version: 2, position: { x: 360, y: 0 }, config: {}, data: {} },
      ],
      edges: [{ id: "e1", source: "ghost", sourcePort: "out", target: "f1", targetPort: "a" }],
    }),
  );
  await page.reload();
  await expect(page.getByText("Unsupported node")).toBeVisible();
  await expect(page.getByText(/Removed 1 broken connection/)).toBeVisible();
  await expect(page.locator(".node--fusion")).toBeVisible();
});

test("newer graph opens read-only", async ({ page }) => {
  await openLab(page);
  await page.evaluate(() => window.__chimera.writeAutosave({ schemaVersion: 7, graphId: "future", nodes: [], edges: [] }));
  await page.reload();
  await expect(page.getByText(/read-only/)).toBeVisible();
});

test("node render crash is contained; app crash offers reload", async ({ page }) => {
  await openLab(page);
  await addPhotos(page, ["lion", "tiger"]);
  const id = await page.evaluate(() => window.__chimera.graph().nodes[0]?.id as string);
  await page.evaluate((n) => window.__chimera.crashNode(n), id);
  await expect(page.getByText("This node failed to render")).toBeVisible();
  await expect(page.locator(".node--fusion")).toBeVisible();
  await page.evaluate(() => window.__chimera.crashApp());
  await expect(page.getByRole("button", { name: "Reload app" })).toBeVisible();
  await page.getByRole("button", { name: "Reload app" }).click();
  await expect(page.locator(".node--fusion")).toBeVisible();
});

test("client-side validation: unsupported, too small, corrupt", async ({ page }) => {
  await openLab(page);
  for (const [file, msg] of [
    ["edge/anim.gif", /isn't supported/],
    ["edge/too_small.jpg", /too small/],
    ["edge/corrupt.jpg", /damaged/],
  ] as const) {
    const chooser = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "Add images" }).click();
    await (await chooser).setFiles([fx(file)]);
    await expect(page.getByText(msg)).toBeVisible();
    await page.evaluate(() => window.__chimera.clearToasts());
  }
  await expect(page.locator(".node")).toHaveCount(0);
});

test("EXIF rotation applied, huge image downscaled on this device before anything is sent", async ({ page }) => {
  await openLab(page);
  await addPhotos(page, ["edge/exif_rotated_gps.jpg", "edge/huge_3000.png"]);
  const meta = await page.locator(".image-node__meta").allTextContents();
  expect(meta.map((m) => m.replace(/\s/g, ""))).toEqual(["400×600", "2048×2048"]);
});

test("same photo twice is blocked before running", async ({ page }) => {
  await openLab(page);
  await addPhotos(page, ["lion", "lion"]);
  await expect(page.getByText(/Both photos are the same image/)).toBeVisible();
  await expect(page.locator(".fusion-node__make")).toBeDisabled();
});

test("rate limited: counts down and tries again by itself", async ({ page }) => {
  await openLab(page, { scenario: "rate_limited" });
  await typeNames(page, "lion", "tiger");
  await make(page);
  await expect(page.locator(".node--fusion [role=alert]")).toContainText("Too many runs were started from here just now.");
  await expect(page.locator(".node--fusion")).toContainText(/Trying again in \d+s/);
  await page.evaluate(() => window.__chimera.mock.scenario("success"));
  await expect(page).toHaveURL(/\?run=/, { timeout: 10_000 });
});
