import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { addImages, fuse, fx, openApp, waitForResult } from "./helpers";

async function axe(page: Page, label: string) {
  const res = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  const bad = res.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${label}: ${v.id} (${v.impact}) ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(" | ")}`)).toEqual([]);
}

/** No horizontal overflow; no clipped text in text containers (PV layout assertions). */
async function layoutOk(page: Page, label: string) {
  const problems = await page.evaluate(() => {
    const out: string[] = [];
    if (document.documentElement.scrollWidth > window.innerWidth + 1) out.push(`page overflows horizontally (${document.documentElement.scrollWidth}px)`);
    const sel = ".node__title, .btn__label, .node__status, .badge, .banner p, .toast__msg, .panel__name, .result-node__name, .step__label, .topbar__title, .empty-state__title";
    document.querySelectorAll<HTMLElement>(sel).forEach((el) => {
      const style = getComputedStyle(el);
      const ellipsis = style.textOverflow === "ellipsis";
      if (!ellipsis && el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0) out.push(`clipped: ${el.className} "${el.textContent?.slice(0, 40)}"`);
    });
    return out;
  });
  expect(problems, label).toEqual([]);
}

for (const theme of ["light", "dark"] as const) {
  test(`axe + layout on main states (${theme})`, async ({ page }) => {
    await page.addInitScript((t) => localStorage.setItem("chimera.theme", t), theme);
    await openApp(page);
    await axe(page, "empty");
    await layoutOk(page, "empty");
    await addImages(page, ["lion", "tiger"]);
    await axe(page, "two connected");
    await fuse(page);
    await waitForResult(page);
    await axe(page, "result");
    await layoutOk(page, "result");
    await page.getByRole("button", { name: "How this was made" }).click();
    await axe(page, "panel");
    await layoutOk(page, "panel");
    await page.keyboard.press("Escape");
    await page.evaluate(() => window.__chimera.setFault("refusal"));
    await page.locator(".fusion-node__fuse").click();
    await expect(page.locator(".node--fusion .node__error")).toBeVisible();
    await axe(page, "error");
    await page.evaluate(() => window.__chimera.force("offline"));
    await axe(page, "offline");
    await layoutOk(page, "offline");
  });
}

test("keyboard only: add two images, fuse, open the result panel", async ({ page }) => {
  await openApp(page);
  const tabTo = async (name: RegExp, max = 80) => {
    for (let i = 0; i < max; i++) {
      await page.keyboard.press("Tab");
      const label = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null;
        return el ? el.getAttribute("aria-label") ?? el.textContent ?? "" : "";
      });
      if (name.test(label.trim())) return;
    }
    throw new Error(`could not tab to ${name}`);
  };
  await tabTo(/^Add images$/);
  const chooser = page.waitForEvent("filechooser");
  await page.keyboard.press("Enter");
  await (await chooser).setFiles([fx("lion"), fx("tiger")]);
  await expect(page.locator(".node--image-input .status--ok")).toHaveCount(2);
  // focus is visible on the next control we reach
  await tabTo(/^Fuse$/);
  const outline = await page.evaluate(() => getComputedStyle(document.activeElement as Element).outlineStyle);
  expect(outline).not.toBe("none");
  await page.keyboard.press("Enter");
  await waitForResult(page);
  await tabTo(/^How this was made$/);
  await page.keyboard.press("Enter");
  await expect(page.getByRole("complementary")).toBeVisible();
  await expect(page.getByRole("button", { name: "Close panel" })).toBeFocused();
});

test("toolbar controls are reachable and at least 32px", async ({ page }) => {
  await openApp(page);
  const sizes = await page.locator(".tool-rail button, .zoom-controls button, .topbar__actions button").evaluateAll((els) =>
    els.map((e) => {
      const r = e.getBoundingClientRect();
      return Math.min(r.width, r.height);
    }),
  );
  expect(sizes.length).toBeGreaterThan(8);
  expect(Math.min(...sizes)).toBeGreaterThanOrEqual(32);
});

test("run status changes are announced (aria-live)", async ({ page }) => {
  await openApp(page);
  await addImages(page, ["lion", "tiger"]);
  await expect(page.locator(".node--fusion [role=status]")).toHaveCount(1);
  await expect(page.locator(".toast-stack")).toHaveAttribute("aria-label", "Notifications");
});

for (const width of [1440, 1280, 1024]) {
  test(`no layout break at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: width === 1024 ? 768 : 800 });
    await openApp(page);
    await layoutOk(page, `empty ${width}`);
    await addImages(page, ["lion", "tiger"]);
    await fuse(page);
    await waitForResult(page);
    await page.getByRole("button", { name: "How this was made" }).click();
    await layoutOk(page, `panel ${width}`);
  });
}
