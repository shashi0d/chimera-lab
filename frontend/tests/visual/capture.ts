/**
 * PV screenshot matrix (TASKSHEET P0-10 / PV-01).
 *
 *   npm run shots -- [--round pv-1] [--states a,b] [--viewports 1440x900,1024x768] [--themes light,dark] [--core]
 *
 * Starts its own mock backend + Vite (test mode), drives the app into each named
 * state, and writes docs/visual-qa/<round>/<viewport>/<theme>/<state>.png plus
 * docs/visual-qa/<round>/manifest.json. Every state is reachable without manual clicks.
 */
import { chromium, type Browser, type Page } from "@playwright/test";
import { spawn, type ChildProcess } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const ROOT = resolve(process.cwd(), "..");
const FX = join(ROOT, "backend/tests/fixtures/images");
const API = 8200;
const WEB = 5175;

const args = new Map<string, string>();
process.argv.slice(2).forEach((a, i, all) => {
  if (a.startsWith("--")) args.set(a.slice(2), all[i + 1] && !all[i + 1]!.startsWith("--") ? all[i + 1]! : "true");
});
const ROUND = args.get("round") ?? "pv-1";
const OUT = join(ROOT, "docs/visual-qa", ROUND);
const VIEWPORTS = (args.get("viewports") ?? "1440x900,1280x800,1024x768").split(",").map((v) => {
  const [w, h] = v.split("x").map(Number);
  return { name: v, width: w!, height: h! };
});
const THEMES = (args.get("themes") ?? "light,dark").split(",") as Array<"light" | "dark">;
const ONLY = args.get("states")?.split(",");

// ------------------------------------------------------------------ helpers

const fx = (n: string) => join(FX, n.includes(".") ? n : `${n}.jpg`);

async function open(page: Page, theme: string) {
  await page.addInitScript((t) => {
    if (!sessionStorage.getItem("shots.init")) {
      localStorage.setItem("chimera.theme", t);
      sessionStorage.setItem("shots.init", "1");
    }
  }, theme);
  await page.goto(`http://localhost:${WEB}/`);
  await page.waitForFunction(() => Boolean((window as unknown as { __chimera?: unknown }).__chimera));
  await page.locator(".workspace[aria-busy=false]").waitFor();
}

async function add(page: Page, names: string[], wait = true) {
  const before = await page.locator(".node--image-input").count();
  const chooser = page.waitForEvent("filechooser");
  const empty = page.getByRole("button", { name: "Add images" });
  if (await empty.isVisible()) await empty.click();
  else await page.getByRole("button", { name: "Add image", exact: true }).click();
  await (await chooser).setFiles(names.map(fx));
  const n = before + Math.min(2, names.length);
  await page.locator(".node--image-input").nth(n - 1).waitFor();
  if (wait) await page.waitForFunction((k) => document.querySelectorAll(".node--image-input .status--ok").length >= k, n, { timeout: 20_000 });
}

async function fuse(page: Page, nth = 0) {
  await page.locator(".fusion-node__fuse").nth(nth).click();
}

async function done(page: Page, versions = 1) {
  await page.waitForFunction(
    (v) => {
      const imgs = document.querySelectorAll(".plate__img.is-loaded").length;
      const label = document.querySelector(".version-switch__label")?.textContent ?? "v1";
      return imgs > 0 && label.includes(`v${v}`) && !document.querySelector(".node.is-running");
    },
    versions,
    { timeout: 30_000 },
  );
}

async function hook<T>(page: Page, fn: string, ...a: unknown[]): Promise<T> {
  return page.evaluate(
    ([f, rest]) => {
      const api = (window as unknown as { __chimera: Record<string, (...x: unknown[]) => unknown> }).__chimera;
      return api[f as string]!(...(rest as unknown[])) as never;
    },
    [fn, a] as const,
  );
}

async function fusionId(page: Page): Promise<string> {
  const g = await hook<{ nodes: Array<{ id: string; type: string }> }>(page, "graph");
  return g.nodes.find((n) => n.type === "fusion")!.id;
}

const STEP_KEYS: Array<[string, string]> = [
  ["load_inputs", "Load images"],
  ["identify", "Identify animals"],
  ["match", "Match field data"],
  ["hybrid_check", "Check real hybrids"],
  ["rules_check", "Check anatomy rules"],
  ["compile", "Plan the creature"],
  ["generate", "Generate image"],
  ["store", "Save result"],
];
const DETAILS = ["Two distinct images loaded", "Lion and Tiger", "A: Lion (tier 1), B: Tiger (tier 1)", "Real hybrid exists: Liger", "10 rules checked, 0 warnings", "Quadruped body, head from A", "Image ready (1 generation)", "Saved with lineage"];

function syntheticRun(nodeId: string, current: number, opts: { agoMs?: number; status?: string; error?: unknown; failedAt?: number } = {}) {
  const now = Date.now();
  const created = now - (opts.agoMs ?? 6000);
  const failedAt = opts.failedAt ?? -1;
  return {
    id: `run_synth_${current}_${opts.status ?? "running"}`,
    graphId: "g",
    nodeId,
    sessionId: null,
    status: opts.status ?? "running",
    result: null,
    error: opts.error ?? null,
    failedInput: null,
    createdAt: new Date(created).toISOString(),
    updatedAt: new Date(now).toISOString(),
    version: 1,
    steps: STEP_KEYS.map(([key, label], i) => {
      const st = i < current ? "succeeded" : i === current ? (failedAt === i ? "failed" : "running") : failedAt >= 0 ? "skipped" : "pending";
      return {
        key,
        label,
        status: st,
        startedAt: i <= current ? new Date(created + i * 700).toISOString() : null,
        endedAt: i < current || st === "failed" ? new Date(created + i * 700 + 600).toISOString() : null,
        detail: st === "succeeded" ? DETAILS[i] : st === "failed" ? "The server stopped." : null,
      };
    }),
  };
}

async function quiet(page: Page, keepToasts = false) {
  if (!keepToasts) await hook(page, "clearToasts");
  await page.mouse.move(2, 600);
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur?.());
  await page.waitForTimeout(350);
}

async function fit(page: Page) {
  await page.getByRole("button", { name: "Fit to view" }).click();
  await page.waitForTimeout(350);
}

// ------------------------------------------------------------------ states

interface State {
  name: string;
  shows: string;
  core?: boolean;
  setup(page: Page): Promise<void>;
}

const errorState = (fault: string, shows: string): State => ({
  name: `30-error-${fault.replace(/_/g, "-")}`,
  shows,
  async setup(page) {
    await add(page, ["lion", "tiger"]);
    await hook(page, "setFault", fault);
    await fuse(page);
    await page.locator(".node--fusion .node__error").waitFor({ timeout: 30_000 });
    if (fault === "rate_limit") await page.waitForTimeout(200);
    await hook(page, "freezeRuns");
    await quiet(page);
  },
});

const STATES: State[] = [
  { name: "01-empty-canvas", shows: "Empty canvas with drop invitation", core: true, setup: async (p) => quiet(p) },
  {
    name: "02-drop-overlay",
    shows: "Files dragged over the canvas",
    async setup(page) {
      await page.evaluate(() => {
        const dt = new DataTransfer();
        dt.items.add(new File(["x"], "a.jpg", { type: "image/jpeg" }));
        document.querySelector(".canvas")!.dispatchEvent(new DragEvent("dragover", { dataTransfer: dt, bubbles: true, cancelable: true }));
      });
      await page.waitForTimeout(200);
    },
  },
  {
    name: "03-one-image",
    shows: "One image, auto-added Fusion node with input A connected",
    core: true,
    async setup(page) {
      await add(page, ["lion"]);
      await quiet(page, true);
    },
  },
  {
    name: "04-uploading",
    shows: "Upload in progress with percent and cancel",
    async setup(page) {
      await page.route("**/assets", async (r) => {
        await new Promise((res) => setTimeout(res, 6000));
        await r.continue().catch(() => undefined);
      });
      await add(page, ["lion"], false);
      await page.evaluate(() => {
        // pin progress at a mid value so the shot is deterministic
        const g = (window as unknown as { __chimera: { graph(): { nodes: Array<{ id: string; type: string }> } } }).__chimera.graph();
        return g.nodes[0]?.id;
      });
      await page.locator(".upload-progress").waitFor();
      await quiet(page);
    },
  },
  {
    name: "05-two-unconnected",
    shows: "Two images, Fusion inputs empty (Fuse disabled with hint)",
    core: true,
    async setup(page) {
      await add(page, ["lion", "tiger"]);
      await page.getByLabel("Connect image A").selectOption("");
      await page.getByLabel("Connect image B").selectOption("");
      await quiet(page);
    },
  },
  {
    name: "06-two-connected",
    shows: "Two images connected, ready to fuse",
    core: true,
    async setup(page) {
      await add(page, ["lion", "tiger"]);
      await quiet(page);
    },
  },
  ...STEP_KEYS.map(([key], i): State => ({
    name: `1${i}-running-${key.replace(/_/g, "-")}`,
    shows: `Fusion running, current step: ${key}`,
    core: i === 6,
    async setup(page) {
      await add(page, ["lion", "tiger"]);
      const id = await fusionId(page);
      await hook(page, "setRun", id, syntheticRun(id, i));
      await quiet(page);
    },
  })),
  {
    name: "18-long-wait",
    shows: "Still working note after 20s",
    async setup(page) {
      await add(page, ["lion", "tiger"]);
      const id = await fusionId(page);
      await hook(page, "setRun", id, syntheticRun(id, 6, { agoMs: 34_000 }));
      await quiet(page);
    },
  },
  {
    name: "19-very-long-wait",
    shows: "After 120s: prominent cancel",
    async setup(page) {
      await add(page, ["lion", "tiger"]);
      const id = await fusionId(page);
      await hook(page, "setRun", id, syntheticRun(id, 6, { agoMs: 128_000 }));
      await quiet(page);
    },
  },
  {
    name: "20-success-real-hybrid",
    shows: "Success with real-hybrid badge (lion + tiger)",
    core: true,
    async setup(page) {
      await add(page, ["lion", "tiger"]);
      await fuse(page);
      await done(page);
      await fit(page);
      await quiet(page);
    },
  },
  {
    name: "21-success-warnings",
    shows: "Success with rule warnings (octopus + macaw)",
    core: true,
    async setup(page) {
      await add(page, ["common_octopus", "scarlet_macaw"]);
      await fuse(page);
      await done(page);
      await fit(page);
      await quiet(page);
    },
  },
  {
    name: "22-version-2",
    shows: "Re-run: version 2 selected in the switcher",
    async setup(page) {
      await add(page, ["red_fox", "green_iguana"]);
      await fuse(page);
      await done(page);
      await page.getByRole("button", { name: "Fuse again" }).click();
      await done(page, 2);
      await fit(page);
      await quiet(page);
    },
  },
  {
    name: "23-panel-open",
    shows: "How this was made panel (top)",
    core: true,
    async setup(page) {
      await add(page, ["lion", "tiger"]);
      await fuse(page);
      await done(page);
      await fit(page);
      await page.getByRole("button", { name: "How this was made" }).click();
      await quiet(page);
    },
  },
  {
    name: "24-panel-notes-prompt",
    shows: "Panel scrolled to field notes and prompt",
    async setup(page) {
      await add(page, ["common_octopus", "scarlet_macaw"]);
      await fuse(page);
      await done(page);
      await page.getByRole("button", { name: "How this was made" }).click();
      await page.locator(".side-panel__scroll").evaluate((el) => el.scrollTo(0, el.scrollHeight));
      await quiet(page);
    },
  },
  {
    name: "25-stale-result",
    shows: "Input replaced after success: results marked outdated",
    async setup(page) {
      await add(page, ["lion", "tiger"]);
      await fuse(page);
      await done(page);
      await page.locator(".node--image-input").first().hover();
      const chooser = page.waitForEvent("filechooser");
      await page.locator(".node--image-input").first().getByRole("button", { name: "Replace image" }).click();
      await (await chooser).setFiles([fx("red_fox")]);
      await page.waitForFunction(() => document.querySelectorAll(".node--image-input .status--ok").length >= 2);
      await fit(page);
      await quiet(page);
    },
  },
  {
    name: "26-result-image-failed",
    shows: "Generated image failed to load: fallback tile with reload",
    async setup(page) {
      await add(page, ["lion", "tiger"]);
      await fuse(page);
      await done(page);
      await page.waitForTimeout(800); // autosave
      const g = await hook<{ nodes: Array<{ type: string; data: { versions?: Array<{ assetId: string }> } }> }>(page, "graph");
      const generated = g.nodes.find((n) => n.type === "result")!.data.versions![0]!.assetId;
      await page.route(new RegExp(`/assets/${generated}/content`), (r) => r.abort());
      await page.reload();
      await page.locator(".plate--failed").waitFor({ timeout: 15_000 });
      await quiet(page);
    },
  },
  errorState("not_animal", "NOT_AN_ANIMAL: message + offending input highlighted"),
  errorState("human", "HUMAN_DETECTED: privacy-safe message + input highlighted"),
  errorState("refusal", "MODEL_REFUSED: what to change, no retry"),
  errorState("server_error", "UPSTREAM_ERROR: Retry fusion"),
  errorState("timeout", "UPSTREAM_TIMEOUT: Retry fusion"),
  errorState("budget", "BUDGET_EXCEEDED: no retry"),
  errorState("rate_limit", "RATE_LIMITED: automatic retry countdown"),
  {
    name: "30-error-interrupted",
    shows: "RUN_INTERRUPTED: server restarted, re-run offered",
    async setup(page) {
      await add(page, ["lion", "tiger"]);
      const id = await fusionId(page);
      await hook(page, "setRun", id, syntheticRun(id, 6, { status: "interrupted", failedAt: 6, error: { code: "RUN_INTERRUPTED", message: "", retryable: true, retryAfterMs: null, details: {}, errorId: null } }));
      await quiet(page);
    },
  },
  {
    name: "30-error-internal",
    shows: "INTERNAL: generic message with reportable error id",
    async setup(page) {
      await add(page, ["lion", "tiger"]);
      const id = await fusionId(page);
      await hook(page, "setRun", id, syntheticRun(id, 5, { status: "failed", failedAt: 5, error: { code: "INTERNAL", message: "", retryable: true, retryAfterMs: null, details: {}, errorId: "7f3a91c2b4e0" } }));
      await quiet(page);
    },
  },
  {
    name: "31-duplicate-inputs",
    shows: "Same image twice: Fuse blocked with hint",
    async setup(page) {
      await add(page, ["lion", "lion"]);
      await quiet(page);
    },
  },
  {
    name: "32-upload-error",
    shows: "Server rejected an upload (IMAGE_CORRUPT)",
    async setup(page) {
      await page.route("**/assets", (r) =>
        r.fulfill({ status: 422, contentType: "application/json", body: JSON.stringify({ error: { code: "IMAGE_CORRUPT", message: "x", retryable: false, details: {} } }) }),
      );
      await add(page, ["lion"], false);
      await page.locator(".node--image-input .image-node__banner--error").waitFor();
      await quiet(page);
    },
  },
  {
    name: "33-unsupported-file-toast",
    shows: "Unsupported file type rejected with toast",
    async setup(page) {
      const chooser = page.waitForEvent("filechooser");
      await page.getByRole("button", { name: "Add images" }).click();
      await (await chooser).setFiles([fx("edge/anim.gif")]);
      await page.locator(".toast").waitFor();
      await quiet(page, true);
    },
  },
  {
    name: "34-too-many-files-toast",
    shows: "Three images dropped: two added, toast explains",
    async setup(page) {
      const chooser = page.waitForEvent("filechooser");
      await page.getByRole("button", { name: "Add images" }).click();
      await (await chooser).setFiles([fx("lion"), fx("tiger"), fx("red_fox")]);
      await page.waitForFunction(() => document.querySelectorAll(".node--image-input .status--ok").length >= 2);
      await quiet(page, true);
    },
  },
  {
    name: "40-offline-banner",
    shows: "Offline banner; Fuse disabled",
    core: true,
    async setup(page) {
      await add(page, ["lion", "tiger"]);
      await hook(page, "force", "offline");
      await quiet(page);
    },
  },
  {
    name: "41-offline-upload-queue",
    shows: "Upload queued while offline",
    async setup(page) {
      await add(page, ["lion"]);
      await hook(page, "force", "offline");
      const chooser = page.waitForEvent("filechooser");
      await page.getByRole("button", { name: "Add image", exact: true }).click();
      await (await chooser).setFiles([fx("tiger")]);
      await page.locator(".node--image-input").nth(1).waitFor();
      await page.waitForTimeout(700); // let the reveal pan finish
      await quiet(page);
    },
  },
  {
    name: "42-server-unreachable",
    shows: "Server unreachable banner (distinct from offline)",
    core: true,
    async setup(page) {
      await add(page, ["lion", "tiger"]);
      await hook(page, "force", "unreachable");
      await quiet(page);
    },
  },
  {
    name: "43-offline-mid-run",
    shows: "Connection lost during a run: polling paused note",
    async setup(page) {
      await add(page, ["lion", "tiger"]);
      const id = await fusionId(page);
      await hook(page, "setRun", id, syntheticRun(id, 6));
      await hook(page, "force", "offline");
      await quiet(page);
    },
  },
  {
    name: "50-node-crash",
    shows: "One node failed to render; canvas still usable",
    core: true,
    async setup(page) {
      await add(page, ["lion", "tiger"]);
      const g = await hook<{ nodes: Array<{ id: string }> }>(page, "graph");
      await hook(page, "crashNode", g.nodes[0]!.id);
      await quiet(page);
    },
  },
  {
    name: "51-app-crash",
    shows: "App-level error screen",
    core: true,
    async setup(page) {
      await hook(page, "crashApp");
      await page.getByRole("button", { name: "Reload app" }).waitFor();
      await quiet(page);
    },
  },
  {
    name: "52-unsupported-node-and-orphans",
    shows: "Unknown node type placeholder + orphan edge toast",
    async setup(page) {
      await hook(page, "writeAutosave", {
        schemaVersion: 1,
        graphId: "broken",
        nodes: [
          { id: "s1", type: "style", version: 3, position: { x: 0, y: 0 }, config: {}, data: {} },
          { id: "f1", type: "fusion", version: 1, position: { x: 320, y: -20 }, config: {}, data: {} },
        ],
        edges: [{ id: "e1", source: "ghost", sourcePort: "out", target: "f1", targetPort: "a" }],
      });
      await page.reload();
      await page.getByText("Unsupported node").waitFor();
      await quiet(page, true);
    },
  },
  {
    name: "53-read-only-newer",
    shows: "Graph from a newer version: read-only banner",
    async setup(page) {
      await hook(page, "writeAutosave", { schemaVersion: 9, graphId: "future", nodes: [{ id: "f1", type: "fusion", position: { x: 0, y: 0 } }], edges: [] });
      await page.reload();
      await page.locator(".banner--readonly").waitFor();
      await quiet(page);
    },
  },
  {
    name: "54-corrupt-autosave",
    shows: "Corrupt autosave discarded with toast",
    async setup(page) {
      await hook(page, "writeAutosave", "garbage{");
      await page.reload();
      await page.locator(".toast").waitFor();
      await quiet(page, true);
    },
  },
  {
    name: "60-fit-view-many-nodes",
    shows: "Fit view with 7 nodes (two fusions)",
    core: true,
    async setup(page) {
      await add(page, ["lion", "tiger"]);
      await fuse(page);
      await done(page);
      await page.getByRole("button", { name: "Add fusion node" }).click();
      await add(page, ["common_octopus", "flamingo"]);
      const fusions = page.locator(".node--fusion");
      await fusions.nth(1).getByLabel("Connect image A").selectOption({ index: 3 });
      await fusions.nth(1).getByLabel("Connect image B").selectOption({ index: 4 });
      await fuse(page, 1);
      await page.waitForFunction(() => document.querySelectorAll(".plate__img.is-loaded").length >= 2, undefined, { timeout: 30_000 });
      await fit(page);
      await quiet(page);
    },
  },
  {
    name: "61-canvas-100-percent",
    shows: "Canvas at 100% zoom after a fusion",
    async setup(page) {
      await add(page, ["scarlet_macaw", "red_fox"]);
      await fuse(page);
      await done(page);
      await quiet(page);
    },
  },
  {
    name: "62-minimap",
    shows: "Minimap toggled on",
    async setup(page) {
      await add(page, ["lion", "tiger"]);
      await page.getByRole("button", { name: "Show minimap" }).click();
      await quiet(page);
    },
  },
  {
    name: "63-refused-connection",
    shows: "Wrong port type: refused with toast",
    async setup(page) {
      await add(page, ["lion", "tiger"]);
      await fuse(page);
      await done(page);
      await hook(page, "clearToasts");
      await page.locator(".node--image-input .port--out").first().dragTo(page.locator(".node--result .port--in"));
      await page.locator(".toast").waitFor();
      await page.mouse.move(2, 600);
      await page.waitForTimeout(250);
    },
  },
  {
    name: "64-shortcuts-dialog",
    shows: "Keyboard shortcuts dialog",
    async setup(page) {
      await page.getByRole("button", { name: "Keyboard shortcuts" }).click();
      await page.waitForTimeout(250);
    },
  },
  {
    name: "80-anatomy-pinned",
    shows: "F1: parts pinned (Head B, Covering A) before fusing",
    core: true,
    async setup(page) {
      await add(page, ["common_octopus", "scarlet_macaw"]);
      await page.getByRole("button", { name: "Head from Auto (model decides)" }).click();
      await page.getByRole("button", { name: "Head from A" }).click();
      await page.getByRole("button", { name: "Covering from Auto (model decides)" }).click();
      await quiet(page);
    },
  },
  {
    name: "81-anatomy-result-panel",
    shows: "F1: result with pinned parts; panel credits you vs model",
    core: true,
    async setup(page) {
      await add(page, ["common_octopus", "scarlet_macaw"]);
      await page.getByRole("button", { name: "Head from Auto (model decides)" }).click();
      await page.getByRole("button", { name: "Head from A" }).click();
      await page.getByRole("button", { name: "Covering from Auto (model decides)" }).click();
      await fuse(page);
      await done(page);
      await fit(page);
      await page.getByRole("button", { name: "How this was made" }).click();
      await page.locator(".side-panel__scroll").evaluate((el) => el.scrollTo(0, (el.querySelector(".donors") as HTMLElement).offsetTop - 120));
      await quiet(page);
    },
  },
  {
    name: "82-anatomy-one-parent",
    shows: "F1: every part pinned to A: advisory hint",
    async setup(page) {
      await add(page, ["lion", "tiger"]);
      for (const part of ["Head", "Body", "Limbs", "Covering", "Tail"]) {
        await page.getByRole("button", { name: `${part} from Auto (model decides)` }).click();
      }
      await quiet(page);
    },
  },
  {
    name: "83-anatomy-outdated",
    shows: "F1: pin changed after a result: result outdated",
    async setup(page) {
      await add(page, ["red_fox", "green_iguana"]);
      await fuse(page);
      await done(page);
      await page.getByRole("button", { name: "Tail from Auto (model decides)" }).click();
      await fit(page);
      await quiet(page);
    },
  },
  {
    name: "90-card-empty",
    shows: "F2: Field card added from a Result, not written yet",
    core: true,
    async setup(page) {
      await add(page, ["lion", "tiger"]);
      await fuse(page);
      await done(page);
      await page.locator(".node--result").hover();
      await page.getByRole("button", { name: "Make field card" }).click();
      await page.waitForTimeout(400);
      await fit(page);
      await quiet(page);
    },
  },
  {
    name: "91-card-written",
    shows: "F2: written field card with invented binomial, ranges and provenance",
    core: true,
    async setup(page) {
      await add(page, ["lion", "tiger"]);
      await fuse(page);
      await done(page);
      await page.locator(".node--result").hover();
      await page.getByRole("button", { name: "Make field card" }).click();
      await page.getByRole("button", { name: "Write card" }).click();
      await page.locator(".field-card__binomial").waitFor({ timeout: 20_000 });
      await fit(page);
      await quiet(page);
    },
  },
  {
    name: "92-card-out-of-date",
    shows: "F2: Result moved to v2; card offers a rewrite",
    async setup(page) {
      await add(page, ["red_fox", "green_iguana"]);
      await fuse(page);
      await done(page);
      await page.locator(".node--result").hover();
      await page.getByRole("button", { name: "Make field card" }).click();
      await page.getByRole("button", { name: "Write card" }).click();
      await page.locator(".field-card__binomial").waitFor({ timeout: 20_000 });
      await page.getByRole("button", { name: "Fuse again" }).click();
      await done(page, 2);
      await fit(page);
      await quiet(page);
    },
  },
  {
    name: "93-card-error-timeout",
    shows: "F2: writing the card timed out: message + retry",
    async setup(page) {
      await add(page, ["lion", "tiger"]);
      await fuse(page);
      await done(page);
      await page.locator(".node--result").hover();
      await page.getByRole("button", { name: "Make field card" }).click();
      await hook(page, "setFault", "timeout");
      await page.getByRole("button", { name: "Write card" }).click();
      await page.locator(".node--field-card .node__error").waitFor({ timeout: 20_000 });
      await hook(page, "freezeRuns");
      await fit(page);
      await quiet(page);
    },
  },
  {
    name: "94-card-exported-png",
    shows: "F2: the downloaded field-card PNG itself (1600×1000)",
    async setup(page) {
      await add(page, ["common_octopus", "scarlet_macaw"]);
      await fuse(page);
      await done(page);
      await page.locator(".node--result").hover();
      await page.getByRole("button", { name: "Make field card" }).click();
      await page.getByRole("button", { name: "Write card" }).click();
      await page.locator(".field-card__binomial").waitFor({ timeout: 20_000 });
      const download = page.waitForEvent("download");
      await page.getByRole("button", { name: "Download PNG" }).click();
      const file = await (await download).path();
      // Show the exported file full-screen so it is captured like any other state.
      const { readFileSync } = await import("node:fs");
      const b64 = readFileSync(file).toString("base64");
      await page.setContent(`<body style="margin:0;background:#888;display:grid;place-items:center;height:100vh"><img src="data:image/png;base64,${b64}" style="max-width:96vw;max-height:96vh"></body>`);
    },
  },
  ...["Add image", "Add fusion node", "Undo", "Fit to view", "Show minimap"].map(
    (label, i): State => ({
      name: `7${i}-focus-${label.toLowerCase().replace(/\s+/g, "-")}`,
      shows: `Keyboard focus on toolbar control: ${label}`,
      async setup(page) {
        await add(page, ["lion", "tiger"]);
        await hook(page, "clearToasts");
        await page.getByRole("button", { name: label, exact: true }).focus();
        await page.keyboard.press("Shift+Tab");
        await page.keyboard.press("Tab");
        await page.waitForTimeout(200);
      },
    }),
  ),
  {
    name: "75-focus-fuse-button",
    shows: "Keyboard focus on the Fuse button",
    async setup(page) {
      await add(page, ["lion", "tiger"]);
      await hook(page, "clearToasts");
      await page.locator(".fusion-node__fuse").focus();
      await page.keyboard.press("Shift+Tab");
      await page.keyboard.press("Tab");
      await page.waitForTimeout(200);
    },
  },
];

// ------------------------------------------------------------------ servers

if (args.has("list")) {
  console.log(JSON.stringify(STATES.map((s) => ({ name: s.name, shows: s.shows, core: Boolean(s.core) }))));
  process.exit(0);
}

function startServers(): ChildProcess[] {
  const py = process.env.PYTHON ?? join(ROOT, ".venv/bin/python");
  const env = {
    ...process.env,
    CHIMERA_MODE: "mock",
    MOCK_DELAY_SCALE: "0.1",
    RETRY_BASE_SECONDS: "0.01",
    RUNS_PER_MINUTE_PER_SESSION: "10000",
    DATA_PATH: "backend/tests/fixtures/chimera_data.sample.json",
    LOCAL_DATA_DIR: join(tmpdir(), `chimera-shots-${Date.now()}`),
    CORS_ORIGINS: `http://localhost:${WEB}`,
  };
  const api = spawn(py, ["-m", "uvicorn", "app.main:app", "--port", String(API), "--log-level", "warning"], { cwd: join(ROOT, "backend"), env, stdio: "ignore" });
  const web = spawn("npx", ["vite", "--mode", "test", "--port", String(WEB), "--strictPort", "--logLevel", "error"], {
    cwd: join(ROOT, "frontend"),
    env: { ...process.env, VITE_API_BASE_URL: `http://localhost:${API}` },
    stdio: "ignore",
  });
  return [api, web];
}

async function waitFor(url: string) {
  for (let i = 0; i < 120; i++) {
    try {
      const r = await fetch(url);
      if (r.ok) return;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`timed out waiting for ${url}`);
}

async function main() {
  const procs = startServers();
  const stop = () => procs.forEach((p) => p.kill());
  process.on("exit", stop);
  let browser: Browser | null = null;
  const manifest: Array<{ file: string; state: string; shows: string; viewport: string; theme: string }> = [];
  const failures: string[] = [];
  try {
    await waitFor(`http://localhost:${API}/health`);
    await waitFor(`http://localhost:${WEB}/`);
    browser = await chromium.launch();
    const states = STATES.filter((s) => (!ONLY || ONLY.some((o) => s.name.startsWith(o))) && (args.has("core") ? s.core : true));
    for (const vp of VIEWPORTS) {
      const small = vp.width < 1440;
      for (const theme of THEMES) {
        const dir = join(OUT, vp.name, theme);
        mkdirSync(dir, { recursive: true });
        for (const s of states) {
          if (small && !s.core && !ONLY) continue; // smaller viewports cover the core states (UI_STANDARD.md)
          const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: 1 });
          const page = await ctx.newPage();
          try {
            await open(page, theme);
            await s.setup(page);
            const file = join(dir, `${s.name}.png`);
            await page.screenshot({ path: file, animations: "disabled" });
            manifest.push({ file: file.replace(`${ROOT}/`, ""), state: s.name, shows: s.shows, viewport: vp.name, theme });
            process.stdout.write(`✓ ${vp.name} ${theme} ${s.name}\n`);
          } catch (e) {
            failures.push(`${vp.name} ${theme} ${s.name}: ${(e as Error).message.split("\n")[0]}`);
            process.stdout.write(`✗ ${vp.name} ${theme} ${s.name}\n`);
          } finally {
            await ctx.close();
          }
        }
      }
    }
  } finally {
    await browser?.close();
    mkdirSync(OUT, { recursive: true });
    // Merge with earlier invocations of the same round (e.g. per-viewport runs).
    const path = join(OUT, "manifest.json");
    const prev = existsSync(path) ? (JSON.parse(readFileSync(path, "utf8")) as { shots: typeof manifest }) : { shots: [] };
    const merged = [...prev.shots.filter((p) => !manifest.some((m) => m.file === p.file)), ...manifest].sort((a, b) => a.file.localeCompare(b.file));
    writeFileSync(path, JSON.stringify({ round: ROUND, captured: merged.length, failures, shots: merged }, null, 2));
    stop();
  }
  console.log(`\n${manifest.length} screenshots in docs/visual-qa/${ROUND}${failures.length ? `, ${failures.length} failed:\n${failures.join("\n")}` : ""}`);
  process.exit(failures.length ? 1 : 0);
}

void main();
