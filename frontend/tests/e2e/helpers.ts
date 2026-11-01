import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";
import { resolve } from "node:path";

export const FIXTURES = resolve(process.cwd(), "../backend/tests/fixtures/images");
export const LIVE = resolve(process.cwd(), "../backend/tests/fixtures/live");
/** Bare names resolve to the real photos (lion, tiger, horse, donkey, bald_eagle, common_octopus). */
export const fx = (name: string) => (name.includes(".") || name.includes("/") ? resolve(FIXTURES, name) : resolve(LIVE, `${name}.webp`));

declare global {
  interface Window {
    __chimera: {
      force(s: "online" | "offline" | "unreachable" | null): void;
      crashNode(id: string): void;
      crashApp(): void;
      loadGraph(raw: unknown): void;
      writeAutosave(raw: unknown): Promise<void>;
      clearToasts(): void;
      graph(): { nodes: Array<{ id: string; type: string; data: Record<string, unknown>; config: Record<string, unknown> }>; edges: unknown[] };
      runs(): Record<string, { status: string; lastEventId: number; items: unknown[] }>;
      transport(): "http" | "mock";
      mock: { scenario(s: string): Promise<void>; stepMs(ms: number): Promise<void>; holdAt(id: number | null): Promise<void>; reset(): Promise<void> };
    };
  }
}

/** Open the app with mock parameters (?mock=, ?mockStep=, ?mockHold=), at a path such as "/?view=lab". */
export async function openApp(page: Page, path = "/", mock: { scenario?: string; stepMs?: number; hold?: number } = {}): Promise<void> {
  const q = new URLSearchParams();
  q.set("mock", mock.scenario ?? "success");
  q.set("mockStep", String(mock.stepMs ?? 120));
  if (mock.hold !== undefined) q.set("mockHold", String(mock.hold));
  const sep = path.includes("?") ? "&" : "?";
  await page.goto(`${path}${sep}${q.toString()}`);
  await page.waitForFunction(() => Boolean(window.__chimera));
  expect(await page.evaluate(() => window.__chimera.transport())).toBe("mock");
}

export async function openLab(page: Page, mock: Parameters<typeof openApp>[2] = {}): Promise<void> {
  await openApp(page, "/?view=lab", mock);
  await expect(page.locator(".workspace[aria-busy=false]")).toBeVisible();
}

/** The contract's name fallback: a Fusion node with two typed names. */
export async function typeNames(page: Page, a: string, b: string): Promise<void> {
  await page.getByRole("button", { name: "Type two names" }).click();
  await page.getByLabel("Animal A").fill(a);
  await page.getByLabel("Animal B").fill(b);
}

/** Uses the native file picker, like a user would. */
export async function addPhotos(page: Page, names: string[]): Promise<void> {
  const chooser = page.waitForEvent("filechooser");
  const empty = page.getByRole("button", { name: "Add images" });
  if (await empty.isVisible()) await empty.click();
  else await page.getByRole("button", { name: "Add image", exact: true }).click();
  const before = await page.locator(".node--image-input").count();
  await (await chooser).setFiles(names.map(fx));
  const expected = before + Math.min(2, names.length);
  await expect(page.locator(".node--image-input .status--ok")).toHaveCount(expected, { timeout: 20_000 });
}

export async function make(page: Page): Promise<void> {
  await page.locator(".fusion-node__make").click();
}

export const trace = (page: Page) => page.getByRole("complementary").filter({ has: page.locator(".trace__title") });
export const log = (page: Page) => page.getByRole("log", { name: "Agent steps" });

export async function waitFinished(page: Page): Promise<void> {
  await expect(page.getByRole("button", { name: "Open creature card" }).first()).toBeVisible({ timeout: 30_000 });
}

export async function axe(page: Page, label: string): Promise<void> {
  const res = await new AxeBuilder({ page: page as never }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  const bad = res.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${label}: ${v.id} (${v.impact}) ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(" | ")}`)).toEqual([]);
}

/** No horizontal page overflow; no clipped text in text containers (PV layout assertions). */
export async function layoutOk(page: Page, label: string): Promise<void> {
  const problems = await page.evaluate(() => {
    const out: string[] = [];
    if (document.documentElement.scrollWidth > window.innerWidth + 1) out.push(`page overflows horizontally (${document.documentElement.scrollWidth}px)`);
    const main = document.querySelector(".main");
    if (main && main.scrollWidth > main.clientWidth + 1) out.push(`main overflows horizontally (${main.scrollWidth}px > ${main.clientWidth}px)`);
    const sel =
      ".node__title, .btn__label, .node__status, .banner p, .toast__msg, .topbar__title, .empty-state__title, .hero__title, .gcard__title, .creature__title, .trace__title, .trace-row__title, .choice__question, .now-card__big, .cblock__title";
    document.querySelectorAll<HTMLElement>(sel).forEach((el) => {
      const style = getComputedStyle(el);
      const ellipsis = style.textOverflow === "ellipsis";
      if (!ellipsis && el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0) out.push(`clipped: ${el.className} "${el.textContent?.slice(0, 40)}"`);
    });
    return out;
  });
  expect(problems, label).toEqual([]);
}
