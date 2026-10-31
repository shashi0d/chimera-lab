import { expect, type Page } from "@playwright/test";
import { resolve } from "node:path";

export const FIXTURES = resolve(process.cwd(), "../backend/tests/fixtures/images");
export const fx = (name: string) => resolve(FIXTURES, name.includes(".") ? name : `${name}.jpg`);

/** Open a drawer section ("Rules and warnings", …) so its contents are visible. */
export async function openSection(page: Page, title: string): Promise<void> {
  const details = page.locator("details.section", { has: page.locator(".section__title", { hasText: title }) });
  if (!(await details.evaluate((d) => (d as HTMLDetailsElement).open))) await details.locator(".section__summary").click();
}

declare global {
  interface Window {
    __chimera: {
      setFault(f: string | null): void;
      force(s: "online" | "offline" | "unreachable" | null): void;
      crashNode(id: string): void;
      crashApp(): void;
      loadGraph(raw: unknown): void;
      writeAutosave(raw: unknown): Promise<void>;
      setRun(nodeId: string, run: unknown): void;
      freezeRuns(): void;
      clearToasts(): void;
      openPanel(id: string): void;
      graph(): { nodes: Array<{ id: string; type: string; data: Record<string, unknown> }>; edges: unknown[] };
      runs(): Record<string, unknown>;
    };
  }
}

export async function openApp(page: Page, query = ""): Promise<void> {
  await page.goto(`/${query}`);
  await page.waitForFunction(() => Boolean(window.__chimera));
  await expect(page.locator(".workspace[aria-busy=false]")).toBeVisible();
}

/** Uses the native file picker, like a user would. */
export async function addImages(page: Page, names: string[], opts: { waitUploaded?: boolean } = {}): Promise<void> {
  const chooser = page.waitForEvent("filechooser");
  const empty = page.getByRole("button", { name: "Add images" });
  if (await empty.isVisible()) await empty.click();
  else await page.getByRole("button", { name: "Add image", exact: true }).click();
  const before = await page.locator(".node--image-input").count();
  await (await chooser).setFiles(names.map(fx));
  const expected = before + Math.min(2, names.length);
  await expect(page.locator(".node--image-input")).toHaveCount(expected, { timeout: 20_000 });
  if (opts.waitUploaded !== false) await expect(page.locator(".node--image-input .status--ok")).toHaveCount(expected, { timeout: 20_000 });
}

export async function fuse(page: Page): Promise<void> {
  await page.locator(".fusion-node__fuse").click();
}

export async function waitForResult(page: Page, versions = 1): Promise<void> {
  await expect(page.locator(".node--fusion .status--ok")).toBeVisible({ timeout: 30_000 });
  await expect(page.locator(".plate__img.is-loaded")).toBeVisible();
  if (versions > 1) await expect(page.locator(".node--result .node__kicker")).toContainText(`v${versions}`);
}

export async function fusionId(page: Page): Promise<string> {
  return page.evaluate(() => window.__chimera.graph().nodes.find((n) => n.type === "fusion")?.id ?? "");
}
