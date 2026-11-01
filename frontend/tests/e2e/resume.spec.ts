import { expect, test } from "@playwright/test";
import { log, make, openApp, openLab, typeNames, waitFinished } from "./helpers";

const stepNumbers = (page: import("@playwright/test").Page) => log(page).locator(".trace-row").count();

test("reload mid-run resumes the trace from the last event, with no step shown twice", async ({ page }) => {
  await openLab(page, { scenario: "success", stepMs: 400 });
  await typeNames(page, "Indian pangolin", "horse");
  await make(page);
  await expect(log(page).getByText("Proposed body plans")).toBeVisible();
  const url = page.url();
  const before = await page.evaluate(() => Object.values(window.__chimera.runs())[0]?.lastEventId ?? 0);
  expect(before).toBeGreaterThan(2);
  await page.reload();
  expect(page.url()).toBe(url);
  // the cached trace is back at once, then the stream continues after it (?after=<last id>)
  await expect(log(page).getByText("Proposed body plans")).toBeVisible();
  await waitFinished(page);
  const ids = await page.evaluate(() => {
    const r = Object.values(window.__chimera.runs())[0] as unknown as { items: Array<{ key: string }> };
    return r.items.map((i) => i.key);
  });
  expect(new Set(ids).size).toBe(ids.length);
  expect(await log(page).getByText("Looked up an animal").count()).toBe(2);
  expect(await stepNumbers(page)).toBeGreaterThan(10);
});

test("coming back to a finished run shows the finished creature", async ({ page }) => {
  await openLab(page, { scenario: "success", stepMs: 60 });
  await typeNames(page, "Indian pangolin", "horse");
  await make(page);
  await waitFinished(page);
  const url = page.url();
  await page.getByRole("link", { name: "Gallery", exact: true }).click();
  await expect(page.locator(".gcard__link")).toHaveCount(6);
  await page.goto(url);
  await expect(page.locator(".result-sum")).toContainText("Indian pangolin × horse");
  await expect(page.locator(".result-sum")).toContainText("Host: horse.");
});

test("a fixture run id opened directly (another device) replays the whole trace and shows the creature", async ({ page }) => {
  await openApp(page, "/?run=run_fx_host_tie");
  await expect(page.locator(".result-sum")).toContainText("tortoise × domestic goat");
  await expect(log(page).getByText(/The agent asked you/)).toBeVisible();
  await expect(log(page).getByText("You chose domestic goat.")).toBeVisible();
});

test("the host-tie question survives a reload and can still be answered", async ({ page }) => {
  await openLab(page, { scenario: "host_tie", stepMs: 80 });
  await typeNames(page, "tortoise", "domestic goat");
  await make(page);
  await expect(page.locator(".choice")).toBeVisible();
  await page.reload();
  const choice = page.locator(".choice");
  await expect(choice).toBeVisible();
  await choice.getByRole("button", { name: "tortoise" }).click();
  await expect(log(page).getByText("You chose tortoise.")).toBeVisible();
  await waitFinished(page);
});

test("the live indicator in the top bar leads back to a running trace", async ({ page }) => {
  await openLab(page, { scenario: "success", stepMs: 600 });
  await typeNames(page, "Indian pangolin", "horse");
  await make(page);
  await expect(page).toHaveURL(/\?run=/);
  const url = page.url();
  await page.getByRole("link", { name: "Gallery", exact: true }).click();
  await page.getByRole("link", { name: /Open its live trace/ }).click();
  expect(page.url()).toBe(url);
  await expect(log(page)).toBeVisible();
});
