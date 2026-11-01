/**
 * R1 screenshot matrix (UI_STANDARD.md): every R1 state at 1440x900 and 390x844, light and dark.
 *
 *   npm run shots -- [--out ../docs/r1/ui_shots] [--states a,b] [--viewports 1440x900,390x844] [--themes light,dark]
 *
 * Starts its own Vite in test mode on 5175 (the mock transport: fixtures, no backend, no model calls) and
 * drives the app into each state through real interactions and the ?mock= parameters.
 */
import { chromium, type Page } from "@playwright/test";
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

const ROOT = resolve(process.cwd(), "..");
const LIVE = join(ROOT, "backend/tests/fixtures/live");
const WEB = 5175;
const args = new Map<string, string>();
process.argv.slice(2).forEach((a, i, all) => {
  if (a.startsWith("--")) args.set(a.slice(2), all[i + 1] && !all[i + 1]!.startsWith("--") ? all[i + 1]! : "true");
});
const OUT = resolve(args.get("out") ?? join(ROOT, "docs/r1/ui_shots"));
const VIEWPORTS = (args.get("viewports") ?? "1440x900,390x844").split(",").map((v) => {
  const [w, h] = v.split("x").map(Number);
  return { name: v, width: w!, height: h! };
});
const THEMES = (args.get("themes") ?? "light,dark").split(",") as Array<"light" | "dark">;
const ONLY = args.get("states")?.split(",");

async function open(page: Page, path: string, mock: { scenario?: string; stepMs?: number; hold?: number } = {}) {
  const q = new URLSearchParams({ mock: mock.scenario ?? "success", mockStep: String(mock.stepMs ?? 60) });
  if (mock.hold !== undefined) q.set("mockHold", String(mock.hold));
  await page.goto(`http://localhost:${WEB}${path}${path.includes("?") ? "&" : "?"}${q}`);
  await page.waitForFunction(() => Boolean((window as unknown as { __chimera?: unknown }).__chimera));
}
async function lab(page: Page, mock: Parameters<typeof open>[2] = {}) {
  await open(page, "/?view=lab", mock);
  await page.locator(".workspace[aria-busy=false]").waitFor();
}
async function names(page: Page, a: string, b: string) {
  await page.getByRole("button", { name: "Type two names" }).click();
  await page.getByLabel("Animal A").fill(a);
  await page.getByLabel("Animal B").fill(b);
}
async function photos(page: Page, files: string[]) {
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Add images" }).click();
  await (await chooser).setFiles(files.map((f) => join(LIVE, `${f}.webp`)));
  await page.locator(".node--image-input .status--ok").nth(files.length - 1).waitFor();
}
const make = (page: Page) => page.locator(".fusion-node__make").click();
async function settle(page: Page) {
  await page.evaluate(() => (window as unknown as { __chimera: { clearToasts(): void } }).__chimera.clearToasts());
  await page.mouse.move(2, 2);
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur?.());
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all([...document.images].filter((i) => !i.complete).map((i) => new Promise((r) => ((i.onload = r), (i.onerror = r)))));
  });
  await page.waitForTimeout(400);
}
async function fit(page: Page) {
  const btn = page.getByRole("button", { name: "Fit to view" });
  if (await btn.isVisible()) await btn.click();
  await page.waitForTimeout(350);
}

const STATES: Array<{ id: string; title: string; go(page: Page): Promise<void> }> = [
  { id: "01-gallery", title: "Gallery (first screen)", go: async (p) => (await open(p, "/"), await p.locator(".gcard__img").nth(3).waitFor()) },
  { id: "02-new-creature", title: "New creature: two photos, mode, Make creature", go: async (p) => (await lab(p), await photos(p, ["common_octopus", "horse"]), await fit(p)) },
  { id: "03-new-creature-names", title: "New creature by names (no photos)", go: async (p) => (await lab(p), await names(p, "Indian pangolin", "horse"), await fit(p)) },
  {
    id: "04-queued",
    title: "Queued with position",
    go: async (p) => {
      await lab(p, { scenario: "queued", stepMs: 60_000 });
      await names(p, "lion", "golden eagle");
      await make(p);
      await p.getByText("Position 2 in the queue").waitFor();
      await fit(p);
    },
  },
  {
    id: "05-trace-mid-run",
    title: "Live trace mid-run",
    go: async (p) => {
      await lab(p, { scenario: "success", stepMs: 60, hold: 12 });
      await names(p, "Indian pangolin", "horse");
      await make(p);
      await p.locator(".trace-img__img").nth(1).waitFor();
      await fit(p);
    },
  },
  {
    id: "06-host-tie",
    title: "needs_choice: host tie",
    go: async (p) => {
      await lab(p, { scenario: "host_tie", stepMs: 60 });
      await names(p, "tortoise", "domestic goat");
      await make(p);
      await p.locator(".choice").waitFor();
      await fit(p);
    },
  },
  {
    id: "07-identify",
    title: "Identify confirmation (POST needs_choice)",
    go: async (p) => {
      await lab(p, { scenario: "identify_choice" });
      await photos(p, ["horse", "donkey"]);
      await fit(p);
      await make(p);
      await p.getByRole("dialog").waitFor();
    },
  },
  {
    id: "08-refused",
    title: "Refused upload (HUMAN_DETECTED)",
    go: async (p) => {
      await lab(p, { scenario: "refused_human" });
      await photos(p, ["lion", "horse"]);
      await make(p);
      await p.locator(".node--fusion [role=alert]").waitFor();
      await fit(p);
    },
  },
  {
    id: "09-daily-cap",
    title: "Daily cap: 429 CAP_REACHED on Make creature",
    go: async (p) => {
      await lab(p, { scenario: "cap_daily" });
      await names(p, "lion", "tiger");
      await make(p);
      await p.locator(".node--fusion [role=alert]").waitFor();
      await fit(p);
    },
  },
  {
    id: "10-daily-cap-gallery",
    title: "Daily cap shown before upload (limits capped)",
    go: async (p) => (await open(p, "/", { scenario: "limits_capped" }), await p.getByText("Today's live creature runs are used up.").waitFor()),
  },
  {
    id: "11-error",
    title: "Run error",
    go: async (p) => {
      await lab(p, { scenario: "error", stepMs: 60 });
      await names(p, "rhinoceros beetle", "brown bear");
      await make(p);
      await p.locator(".trace .now-card--error").waitFor({ timeout: 20_000 });
      await fit(p);
    },
  },
  {
    id: "12-trace-finished",
    title: "Trace finished: the creature leads",
    go: async (p) => {
      await lab(p, { scenario: "success", stepMs: 40 });
      await names(p, "Indian pangolin", "horse");
      await make(p);
      await p.locator(".result-sum__img").waitFor({ timeout: 20_000 });
      await fit(p);
    },
  },
  { id: "13-card-overlay-off", title: "Creature card, anatomy map off", go: async (p) => (await open(p, "/?creature=crt_fx_b09"), await p.locator(".creature__img").waitFor()) },
  {
    id: "14-card-overlay-on",
    title: "Creature card, anatomy map on with legend",
    go: async (p) => {
      await open(p, "/?creature=crt_fx_b10");
      await p.getByRole("button", { name: "Anatomy map" }).click();
      if ((p.viewportSize()?.width ?? 1440) < 700) await p.locator(".creature__overlay").evaluate((el) => el.scrollIntoView({ block: "end" }));
    },
  },
  {
    id: "15-both-picks",
    title: "Both picks (agent and code ranking disagree)",
    go: async (p) => {
      await open(p, "/?creature=crt_mock_b10_split");
      await p.locator(".cblock--picks").evaluate((el) => el.scrollIntoView({ block: "start" }));
    },
  },
];

async function main() {
  const vite = spawn("npx", ["vite", "--mode", "test", "--port", String(WEB), "--strictPort"], { stdio: "ignore", env: { ...process.env, VITE_EVO_TRANSPORT: "mock" } });
  try {
    for (let i = 0; i < 60; i++) {
      try {
        if ((await fetch(`http://localhost:${WEB}/`)).ok) break;
      } catch {
        /* not up yet */
      }
      await new Promise((r) => setTimeout(r, 500));
    }
    const browser = await chromium.launch();
    const manifest: Array<Record<string, string>> = [];
    for (const vp of VIEWPORTS) {
      for (const theme of THEMES) {
        const dir = join(OUT, vp.name, theme);
        mkdirSync(dir, { recursive: true });
        for (const s of STATES.filter((x) => !ONLY || ONLY.includes(x.id))) {
          const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: 1 });
          await ctx.addInitScript((t) => localStorage.setItem("chimera.theme", t), theme);
          const page = await ctx.newPage();
          try {
            await s.go(page);
            await settle(page);
            const file = join(dir, `${s.id}.png`);
            await page.screenshot({ path: file });
            manifest.push({ state: s.id, title: s.title, viewport: vp.name, theme, file: file.replace(`${ROOT}/`, "") });
            console.log("ok", vp.name, theme, s.id);
          } catch (e) {
            console.error("FAILED", vp.name, theme, s.id, String(e).split("\n")[0]);
          }
          await ctx.close();
        }
      }
    }
    await browser.close();
    writeFileSync(join(OUT, "manifest.json"), JSON.stringify(manifest, null, 2));
  } finally {
    vite.kill();
  }
}

void main();
