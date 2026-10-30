import { expect, test } from "@playwright/test";
import { addImages, fuse, openApp, waitForResult } from "./helpers";

const CASES: Array<{ fault: string; text: RegExp; retry: boolean; flagged?: number }> = [
  { fault: "not_animal", text: /couldn't find an animal/, retry: false, flagged: 1 },
  { fault: "human", text: /shows a person/, retry: false, flagged: 0 },
  { fault: "refusal", text: /declined this pair/, retry: false },
  { fault: "server_error", text: /model service had a problem/, retry: true },
  { fault: "timeout", text: /took too long/, retry: true },
  { fault: "corrupt_output", text: /model service had a problem/, retry: true },
  { fault: "budget", text: /budget is used up/, retry: false },
];

for (const c of CASES) {
  test(`fault ${c.fault} maps to a clear message`, async ({ page }) => {
    await openApp(page);
    await addImages(page, ["lion", "tiger"]);
    await page.evaluate((f) => window.__chimera.setFault(f), c.fault);
    await fuse(page);
    const alert = page.locator(".node--fusion .node__error");
    await expect(alert).toContainText(c.text, { timeout: 30_000 });
    await expect(page.locator(".node--fusion .step--failed")).toHaveCount(1);
    await expect(page.getByRole("button", { name: "Retry fusion" })).toHaveCount(c.retry ? 1 : 0);
    if (c.flagged !== undefined) {
      await expect(page.locator(".node--image-input").nth(c.flagged)).toHaveClass(/is-flagged/);
    }
    // recovery: clear the fault and fuse again
    await page.evaluate(() => window.__chimera.setFault(null));
    await page.locator(".fusion-node__fuse").click();
    await waitForResult(page);
    await expect(page.locator(".node--image-input.is-flagged")).toHaveCount(0);
  });
}

test("rate limit counts down and retries automatically", async ({ page }) => {
  await openApp(page);
  await addImages(page, ["lion", "tiger"]);
  await page.evaluate(() => window.__chimera.setFault("rate_limit"));
  await fuse(page);
  await expect(page.getByText(/Retrying in \ds/)).toBeVisible({ timeout: 30_000 });
  await page.evaluate(() => window.__chimera.setFault(null));
  await waitForResult(page);
});

test("cancel a running fusion", async ({ page }) => {
  await openApp(page);
  await addImages(page, ["lion", "tiger"]);
  await page.evaluate(() => window.__chimera.setFault("slow"));
  await fuse(page);
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.locator(".node--fusion .node__status")).toHaveText(/Cancelled/);
  await expect(page.locator(".fusion-node__fuse")).toBeEnabled();
});

test("crash mid-run, then backend lease marks it interrupted (UI offers re-run)", async ({ page }) => {
  await openApp(page);
  await addImages(page, ["lion", "tiger"]);
  const id = await page.evaluate(() => window.__chimera.graph().nodes.find((n) => n.type === "fusion")?.id as string);
  // Synthetic interrupted run: the real lease is 3 minutes, covered by backend tests.
  await page.evaluate((nodeId) => {
    window.__chimera.setRun(nodeId, {
      id: "run_interrupted", graphId: "g", nodeId, sessionId: null, status: "interrupted", result: null, failedInput: null,
      steps: [{ key: "load_inputs", label: "Load images", status: "succeeded", startedAt: null, endedAt: null, detail: null },
              { key: "generate", label: "Generate image", status: "skipped", startedAt: null, endedAt: null, detail: null }],
      error: { code: "RUN_INTERRUPTED", message: "", retryable: true, retryAfterMs: null, details: {}, errorId: null },
      createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(), version: 1,
    });
  }, id);
  await expect(page.getByText(/server restarted/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry fusion" })).toBeEnabled();
});
