import { expect, test, type Page } from "@playwright/test";
import { addPhotos, axe, layoutOk, log, make, openApp, openLab, typeNames, waitFinished } from "./helpers";

const theme = (page: Page, t: "light" | "dark") => page.addInitScript((v) => localStorage.setItem("chimera.theme", v), t);

for (const t of ["light", "dark"] as const) {
  test(`axe 0 serious/critical + layout on the main states (${t})`, async ({ page }) => {
    await theme(page, t);
    await openApp(page);
    await expect(page.locator(".gcard__link")).toHaveCount(6);
    await axe(page, "gallery");
    await layoutOk(page, "gallery");

    await openApp(page, "/?creature=crt_fx_b09");
    await page.getByRole("button", { name: "Anatomy map" }).click();
    await axe(page, "creature + overlay");
    await layoutOk(page, "creature");
    await openApp(page, "/?creature=crt_mock_b10_split");
    await expect(page.locator(".pick")).toHaveCount(2);
    await axe(page, "both picks");

    await openLab(page, { scenario: "queued", stepMs: 2000 });
    await axe(page, "lab empty");
    await typeNames(page, "lion", "golden eagle");
    await make(page);
    await expect(page.getByText("Position 2 in the queue")).toBeVisible();
    await axe(page, "queued");

    await openLab(page, { scenario: "host_tie", stepMs: 80 });
    await page.locator(".node--fusion").waitFor();
    await make(page).catch(() => undefined);
    if (!(await page.locator(".choice").isVisible())) {
      await page.evaluate(() => window.__chimera.loadGraph({ schemaVersion: 1, graphId: "a", nodes: [], edges: [] }));
      await typeNames(page, "tortoise", "domestic goat");
      await make(page);
    }
    await expect(page.locator(".choice")).toBeVisible();
    await axe(page, "host tie choice");
    await layoutOk(page, "host tie");
    await page.locator(".choice").getByRole("button", { name: "domestic goat" }).click();
    await waitFinished(page);
    await axe(page, "finished trace");

    await openLab(page, { scenario: "identify_choice" });
    await page.evaluate(() => window.__chimera.loadGraph({ schemaVersion: 1, graphId: "b", nodes: [], edges: [] }));
    await addPhotos(page, ["lion", "horse"]);
    await make(page);
    await expect(page.getByRole("dialog")).toBeVisible();
    await axe(page, "identify dialog");
    await page.getByRole("dialog").getByRole("button", { name: "Cancel" }).click();

    await openLab(page, { scenario: "refused_human" });
    await make(page);
    await expect(page.locator(".node--fusion [role=alert]")).toBeVisible();
    await axe(page, "refused upload");

    await openLab(page, { scenario: "error", stepMs: 60 });
    await page.evaluate(() => window.__chimera.loadGraph({ schemaVersion: 1, graphId: "c", nodes: [], edges: [] }));
    await typeNames(page, "rhinoceros beetle", "brown bear");
    await make(page);
    await expect(page.locator(".trace .now-card--error")).toBeVisible({ timeout: 20_000 });
    await axe(page, "run error");

    await openApp(page, "/", { scenario: "limits_capped" });
    await expect(page.getByText("Today's live creature runs are used up.")).toBeVisible();
    await axe(page, "capped gallery");
    await page.evaluate(() => window.__chimera.force("offline"));
    await axe(page, "offline");
  });
}

test("keyboard only: gallery → new creature → names → make → answer the host tie → open the card", async ({ page }) => {
  await openApp(page, "/", { scenario: "host_tie", stepMs: 80 });
  const tabTo = async (name: RegExp, max = 60) => {
    for (let i = 0; i < max; i++) {
      await page.keyboard.press("Tab");
      const label = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null;
        return el ? (el.getAttribute("aria-label") ?? el.textContent ?? "").trim() : "";
      });
      if (name.test(label)) return;
    }
    throw new Error(`could not tab to ${name}`);
  };
  await tabTo(/^Make a new creature$/);
  expect(await page.evaluate(() => getComputedStyle(document.activeElement as Element).outlineStyle)).not.toBe("none");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/view=lab/);
  await tabTo(/^Type two names$/);
  await page.keyboard.press("Enter");
  await page.keyboard.press("Tab"); // the first name field is focused for you; Tab moves on after typing
  await page.getByLabel("Animal A").focus();
  await page.keyboard.type("tortoise");
  await page.keyboard.press("Tab");
  await page.keyboard.type("domestic goat");
  await tabTo(/^Make creature$/);
  await page.keyboard.press("Enter");
  await expect(page.locator(".choice")).toBeVisible();
  await tabTo(/^domestic goat$/, 80);
  await page.keyboard.press("Enter");
  await expect(log(page).getByText("You chose domestic goat.")).toBeVisible();
  await waitFinished(page);
  await page.locator(".result-sum").getByRole("button", { name: "Open creature card" }).focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\?creature=crt_fx_b10$/);
  await tabTo(/^Anatomy map$/);
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: "Anatomy map" })).toHaveAttribute("aria-pressed", "true");
});

test("top bar and canvas controls are at least 32px", async ({ page }) => {
  await openLab(page);
  const sizes = await page.locator(".tool-rail button, .zoom-controls button, .topbar__actions button").evaluateAll((els) =>
    els.map((e) => {
      const r = e.getBoundingClientRect();
      return Math.min(r.width, r.height);
    }),
  );
  expect(sizes.length).toBeGreaterThan(8);
  expect(Math.min(...sizes)).toBeGreaterThanOrEqual(32);
});

for (const [w, h] of [[390, 844], [1024, 768], [1440, 900]] as const) {
  test(`no layout break at ${w}px: gallery, trace, creature card`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    await openApp(page);
    await expect(page.locator(".gcard__link")).toHaveCount(6);
    await layoutOk(page, `gallery ${w}`);
    await openLab(page, { scenario: "host_tie", stepMs: 80 });
    await layoutOk(page, `lab ${w}`);
    await typeNames(page, "tortoise", "domestic goat");
    await make(page);
    await expect(page.locator(".choice")).toBeVisible();
    await layoutOk(page, `trace ${w}`);
    await openApp(page, "/?creature=crt_mock_b10_split");
    await expect(page.locator(".pick")).toHaveCount(2);
    await layoutOk(page, `creature ${w}`);
  });
}
