import { expect, test, type Page } from "@playwright/test";
import { addPhotos, log, make, trace, typeNames } from "../e2e/helpers";

// R1 lead: one mock end-to-end per fixture, from the built UI through the REAL backend (job runner, event store,
// SSE, caps, gallery, creature store) in mock mode. The X-Mock-Scenario header picks the fixture the backend replays.

async function scenario(page: Page, name: string, opts: { limits?: boolean } = {}) {
  await page.route(/\/evo\/agent\/(runs|limits)(\?.*)?$/, async (route) => {
    const req = route.request();
    if (req.method() === "POST" || (opts.limits && req.url().includes("/limits"))) {
      await route.continue({ headers: { ...req.headers(), "x-mock-scenario": name } });
    } else await route.continue();
  });
}

async function lab(page: Page) {
  await page.goto("/?view=lab");
  await expect(page.locator(".workspace[aria-busy=false]")).toBeVisible();
}

const finished = (page: Page) => expect(page.getByRole("button", { name: "Open creature card" }).first()).toBeVisible({ timeout: 60_000 });

test("served from one origin with the real transport; gallery shows the six showcase creatures from the backend", async ({ page }) => {
  await page.goto("/");
  expect(await page.evaluate(() => (window as unknown as { __chimera?: unknown }).__chimera)).toBeUndefined(); // production build
  const cards = page.locator(".gcard__link");
  await expect(cards).toHaveCount(6);
  for (let i = 0; i < 6; i++) await expect(cards.nth(i).getByText("Generated fusion")).toBeVisible();
  await cards.first().click();
  await expect(page).toHaveURL(/\?creature=/);
  await expect(page.locator(".creature__img")).toBeVisible();
  const w = await page.locator(".creature__img").evaluate(async (i: HTMLImageElement) => (await i.decode().then(() => i.naturalWidth).catch(() => 0)));
  expect(w).toBeGreaterThan(0);
});

test("success: a run streams, finalizes, saves a creature, and the gallery lists it", async ({ page }) => {
  await scenario(page, "success");
  await lab(page);
  await typeNames(page, "Indian pangolin", "horse");
  await make(page);
  await expect(page).toHaveURL(/\?run=/);
  await expect(trace(page)).toBeVisible();
  await expect(log(page).getByText("Chose a body plan")).toBeVisible({ timeout: 60_000 });
  await finished(page);
  await page.locator(".result-sum").getByRole("button", { name: "Open creature card" }).click();
  await expect(page).toHaveURL(/\?creature=/);
  await expect(page.getByText("Generated fusion").first()).toBeVisible();
  const w = await page.locator(".creature__img").evaluate(async (i: HTMLImageElement) => (await i.decode().then(() => i.naturalWidth).catch(() => 0)));
  expect(w).toBeGreaterThan(0);
  await page.goto("/");
  await expect(page.locator(".gcard__link").nth(6)).toBeVisible(); // the six showcase creatures plus this run
});

test("resume: reloading mid-run continues from the last event without duplicates", async ({ page }) => {
  await scenario(page, "success");
  await lab(page);
  await typeNames(page, "Indian pangolin", "horse");
  await make(page);
  await expect(log(page).getByText("Chose a body plan")).toBeVisible({ timeout: 60_000 });
  await page.reload();
  await finished(page);
  const texts = await log(page).locator("li").allTextContents();
  expect(new Set(texts).size).toBe(texts.length);
});

test("host_tie: the agent asks, the answer is posted to the backend, the run finishes with the chosen host", async ({ page }) => {
  await scenario(page, "host_tie");
  await lab(page);
  await typeNames(page, "tortoise", "domestic goat");
  await make(page);
  const choice = page.locator(".choice");
  await expect(choice).toBeVisible({ timeout: 60_000 });
  await choice.getByRole("button", { name: "domestic goat" }).click();
  await expect(log(page).getByText("You chose domestic goat.")).toBeVisible({ timeout: 30_000 });
  await finished(page);
  await expect(page.locator(".result-sum")).toContainText("domestic goat");
});

test("identify_choice: the backend asks which animal; confirming starts a run", async ({ page }) => {
  await scenario(page, "identify_choice");
  await lab(page);
  await addPhotos(page, ["lion", "horse"]);
  await make(page);
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByRole("radio").first().check();
  await dialog.getByRole("button", { name: "Use this animal" }).click();
  await expect(page).toHaveURL(/\?run=/);
});

test("cap: the per-run render cap is a notice; the run still finalizes", async ({ page }) => {
  await scenario(page, "cap");
  await lab(page);
  await typeNames(page, "common octopus", "horse");
  await make(page);
  await expect(log(page).getByText(/Render limit reached/)).toBeVisible({ timeout: 60_000 });
  await finished(page);
});

test("queued: the queue position shows, then the run starts and finishes", async ({ page }) => {
  await scenario(page, "queued");
  await lab(page);
  await typeNames(page, "lion", "golden eagle");
  await make(page);
  await expect(page.getByText(/Position \d in the queue/)).toBeVisible({ timeout: 30_000 });
  await finished(page);
});

test("error: the run fails mid-way and the trace says so", async ({ page }) => {
  await scenario(page, "error");
  await lab(page);
  await typeNames(page, "rhinoceros beetle", "brown bear");
  await make(page);
  await expect(page.locator(".node--fusion")).toContainText("Failed", { timeout: 60_000 });
  await expect(page.locator(".trace").getByRole("button", { name: "Try again" })).toBeVisible();
});

for (const [name, text] of [
  ["refused_human", "This looks like a photo of a person."],
  ["refused_type", "That file type isn't supported."],
  ["refused_size", "That image is too large."],
  ["refused_animal", "We couldn't find an animal in this image."],
] as const) {
  test(`${name}: the backend refuses and the UI explains it`, async ({ page }) => {
    await scenario(page, name);
    await lab(page);
    await addPhotos(page, ["lion", "horse"]);
    await make(page);
    await expect(page.locator(".node--fusion [role=alert]")).toContainText(text);
    await expect(page).toHaveURL(/view=lab/);
  });
}

test("cap_daily: 429 CAP_REACHED from the backend switches the app to the capped state; the gallery still works", async ({ page }) => {
  await scenario(page, "cap_daily");
  await lab(page);
  await typeNames(page, "lion", "tiger");
  await make(page);
  await expect(page.locator(".node--fusion [role=alert]")).toContainText("Today's live creature runs are used up.");
  await page.goto("/");
  await expect(page.locator(".gcard__link").first()).toBeVisible();
});

test("cap_daily via limits: the capped state shows before any upload, and the gallery still works", async ({ page }) => {
  await scenario(page, "cap_daily", { limits: true });
  await page.goto("/");
  await expect(page.getByText("Today's live creature runs are used up.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Make a new creature" })).toBeDisabled();
  expect(await page.locator(".gcard__link").count()).toBeGreaterThanOrEqual(6); // earlier tests add creatures
});

test("an unknown run id gets 404 from the backend and the UI says so", async ({ page }) => {
  await page.goto("/?run=run_does_not_exist");
  await expect(page.getByText("This run can't be found.")).toBeVisible();
});
