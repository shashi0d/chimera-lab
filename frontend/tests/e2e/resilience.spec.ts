import { expect, test } from "@playwright/test";
import { addImages, fuse, fx, openApp, waitForResult } from "./helpers";

test("offline: banner, Fuse disabled, uploads queue and resume on reconnect", async ({ page, context }) => {
  await openApp(page);
  await addImages(page, ["lion"]);
  await context.setOffline(true);
  await expect(page.getByText(/You're offline/).first()).toBeVisible();
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Add image", exact: true }).click();
  await (await chooser).setFiles([fx("tiger")]);
  await expect(page.locator(".node--image-input").nth(1)).toContainText("Waiting for connection");
  await expect(page.locator(".fusion-node__fuse")).toBeDisabled();
  // editing still works offline
  await page.locator(".node--image-input").first().click();
  await context.setOffline(false);
  await expect(page.locator(".node--image-input .status--ok")).toHaveCount(2, { timeout: 20_000 });
  await expect(page.locator(".banner--offline")).toHaveCount(0);
});

test("connection drops mid-run: polling pauses, then shows the final state", async ({ page, context }) => {
  await openApp(page);
  await addImages(page, ["lion", "tiger"]);
  await page.evaluate(() => window.__chimera.setFault("slow"));
  await fuse(page);
  await expect(page.locator(".step--running")).toBeVisible();
  await context.setOffline(true);
  await expect(page.getByText(/keeps running on the server/)).toBeVisible();
  await page.waitForTimeout(1500);
  await context.setOffline(false);
  await waitForResult(page);
});

test("server unreachable while online shows a distinct banner", async ({ page }) => {
  await openApp(page);
  await page.route("**/health", (r) => r.abort());
  await page.evaluate(() => window.dispatchEvent(new Event("online")));
  await expect(page.locator(".banner--unreachable")).toBeVisible();
  await expect(page.locator(".banner--offline")).toHaveCount(0);
  await page.unroute("**/health");
  await page.getByRole("button", { name: "Try now" }).click();
  await expect(page.locator(".banner--unreachable")).toHaveCount(0);
});

test("reload mid-run resumes the run", async ({ page }) => {
  await openApp(page);
  await addImages(page, ["lion", "tiger"]);
  await page.evaluate(() => window.__chimera.setFault("slow"));
  await fuse(page);
  await expect(page.locator(".step--running")).toBeVisible();
  await page.waitForTimeout(700); // let autosave persist the run id
  await page.reload();
  await expect(page.locator(".node--fusion .steps")).toBeVisible();
  await waitForResult(page);
});

test("corrupt autosave: discarded with a toast, app starts clean", async ({ page }) => {
  await openApp(page);
  await page.evaluate(() => window.__chimera.writeAutosave("garbage{"));
  await page.reload();
  await expect(page.getByText(/couldn't be read/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Start with two animals" })).toBeVisible();
});

test("broken saved graph: unknown node placeholder, orphan edges removed", async ({ page }) => {
  await openApp(page);
  await page.evaluate(() =>
    window.__chimera.writeAutosave({
      schemaVersion: 1,
      graphId: "broken",
      nodes: [
        { id: "s1", type: "style", version: 3, position: { x: 0, y: 0 }, config: {}, data: {} },
        { id: "f1", type: "fusion", version: 1, position: { x: 320, y: 0 }, config: {}, data: {} },
      ],
      edges: [{ id: "e1", source: "ghost", sourcePort: "out", target: "f1", targetPort: "a" }],
    }),
  );
  await page.reload();
  await expect(page.getByText("Unsupported node")).toBeVisible();
  await expect(page.getByText(/Removed 1 broken connection/)).toBeVisible();
  await expect(page.locator(".node--fusion")).toBeVisible();
});

test("legacy v0 graph migrates; newer graph opens read-only", async ({ page }) => {
  await openApp(page);
  await page.evaluate(() =>
    window.__chimera.writeAutosave({ schemaVersion: 0, id: "legacy", nodes: [{ id: "f1", type: "fusion", pos: { x: 10, y: 10 } }], links: [] }),
  );
  await page.reload();
  await expect(page.locator(".node--fusion")).toBeVisible();
  await page.evaluate(() => window.__chimera.writeAutosave({ schemaVersion: 7, graphId: "future", nodes: [], edges: [] }));
  await page.reload();
  await expect(page.getByText(/read-only/)).toBeVisible();
});

test("node render crash is contained; app crash offers reload", async ({ page }) => {
  await openApp(page);
  await addImages(page, ["lion", "tiger"]);
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
  await openApp(page);
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

test("EXIF rotation applied, huge image downscaled before upload", async ({ page }) => {
  await openApp(page);
  await addImages(page, ["edge/exif_rotated_gps.jpg", "edge/huge_3000.png"]);
  const meta = await page.locator(".image-node__meta").allTextContents();
  expect(meta.map((m) => m.replace(/\s/g, ""))).toEqual(["400×600", "2048×2048"]);
});

test("same image twice is blocked before running", async ({ page }) => {
  await openApp(page);
  await addImages(page, ["lion", "lion"]);
  await expect(page.getByText(/Both inputs are the same image/)).toBeVisible();
  await expect(page.locator(".fusion-node__fuse")).toBeDisabled();
});
