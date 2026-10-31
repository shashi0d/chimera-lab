import type { Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

// U1: put real L1 results on the canvas for screenshots and visual baselines: the live input
// photos (added through the UI like a user would), the live fusion image, and the recorded
// live run and spec (docs/live/fusions/<case>.json). Used by capture.ts and visual.spec.ts.

const HERE = dirname(fileURLToPath(import.meta.url));
export const LIVE_INPUTS = resolve(HERE, "../../../backend/tests/fixtures/live");
export const LIVE_FUSIONS = resolve(HERE, "../../../docs/live/fusions");

interface LiveRun {
  id: string;
  updatedAt: string;
  inputs: { A: string; B: string; donors: Record<string, string> | null };
  result: { assetId: string; creatureId: string; imageUrl: string; spec: { parents: Array<{ slot: string; assetId: string }> }; metaResponseId: string | null; savedImage?: string };
  [k: string]: unknown;
}

type Doc = {
  graphId: string;
  nodes: Array<{ id: string; type: string; version: number; position: { x: number; y: number }; config: Record<string, unknown>; data: Record<string, unknown> }>;
  edges: Array<Record<string, string>>;
};

export function liveRun(name: string): LiveRun {
  return JSON.parse(readFileSync(join(LIVE_FUSIONS, `${name}.json`), "utf8")) as LiveRun;
}

async function upload(api: string, path: string): Promise<{ assetId: string; url: string }> {
  const form = new FormData();
  form.append("file", new Blob([readFileSync(path)], { type: "image/webp" }), path.split("/").pop()!);
  const r = await fetch(`${api}/assets`, { method: "POST", body: form, headers: { "X-Session-Id": "shots" } });
  if (!r.ok) throw new Error(`upload failed: ${r.status}`);
  return (await r.json()) as { assetId: string; url: string };
}

/**
 * Several cases become versions v1…vN of one Result node. `addInputs` must add the first case's
 * two input photos (A then B) through the UI and wait for their uploads.
 */
export async function seedLive(page: Page, cases: string[], opts: { api: string; addInputs(files: string[]): Promise<void> }): Promise<void> {
  const runs = cases.map(liveRun);
  const first = runs[0]!;
  await opts.addInputs([join(LIVE_INPUTS, first.inputs.A), join(LIVE_INPUTS, first.inputs.B)]);
  const doc = (await page.evaluate(() => (window as unknown as { __chimera: { graph(): unknown } }).__chimera.graph())) as Doc;
  // Later nodes win, so a re-added photo maps to its newest upload.
  const byFile = new Map(doc.nodes.filter((n) => n.type === "image-input").map((n) => [n.data.fileName as string, n.data.assetId as string]));
  // The Fusion wired to the inputs just added (a canvas may already hold other pairs).
  const inputA = [...doc.nodes].reverse().find((n) => n.type === "image-input" && n.data.fileName === first.inputs.A);
  const wired = doc.edges.find((e) => e.source === inputA?.id && e.targetPort === "a")?.target;
  const fusion = doc.nodes.find((n) => n.id === wired) ?? doc.nodes.find((n) => n.type === "fusion")!;
  const versions = [];
  const patched = [];
  for (const [i, run] of runs.entries()) {
    const asset = await upload(opts.api, join(LIVE_FUSIONS, `${cases[i]}.webp`));
    const imageUrl = `${asset.url}?live=1`;
    const spec = structuredClone(run.result.spec);
    for (const p of spec.parents) p.assetId = byFile.get(run.inputs[p.slot as "A" | "B"]) ?? p.assetId;
    const { inputs: _inputs, ...rest } = run;
    const { savedImage: _saved, ...result } = run.result;
    patched.push({ ...rest, nodeId: fusion.id, graphId: doc.graphId, result: { ...result, assetId: asset.assetId, imageUrl, spec } });
    versions.push({ runId: run.id, assetId: asset.assetId, creatureId: run.result.creatureId, imageUrl, spec, createdAt: run.updatedAt, metaResponseId: run.result.metaResponseId });
  }
  const last = runs[runs.length - 1]!;
  if (last.inputs.donors) {
    // Pins are per slot; if the last case has its parents the other way round, swap them.
    const flip = last.inputs.A !== first.inputs.A;
    const swap: Record<string, string> = { A: "B", B: "A", auto: "auto" };
    const donors = Object.fromEntries(Object.entries(last.inputs.donors).map(([k, v]) => [k, flip ? swap[v] ?? v : v]));
    fusion.config = { ...fusion.config, donors };
  }
  fusion.data = { ...fusion.data, runIds: runs.map((r) => r.id), activeRunId: last.id };
  doc.nodes.push({ id: "result-live", type: "result", version: 1, position: { x: fusion.position.x + 380, y: fusion.position.y - 20 }, config: {}, data: { versions, selected: versions.length - 1 } });
  doc.edges.push({ id: "e-live-result", source: fusion.id, sourcePort: "out", target: "result-live", targetPort: "in" });
  await page.evaluate(
    ([d, id, run]) => {
      const api = (window as unknown as { __chimera: { loadGraph(x: unknown): void; setRun(n: string, r: unknown): void } }).__chimera;
      api.loadGraph(d);
      api.setRun(id as string, run);
    },
    [doc, fusion.id, patched[patched.length - 1]] as const,
  );
  await page.locator(".plate__img.is-loaded").waitFor({ timeout: 15_000 });
}

/**
 * Mock runs still drive the pipeline (faults, cards, versions behave for real), but any generated
 * asset is served as a live fusion image. Input photos and seeded live results pass through.
 */
export async function routeLiveResults(page: Page, fusionFor: () => string): Promise<void> {
  await page.route(/\/assets\/[^/]+\/content/, async (route) => {
    const url = route.request().url();
    const id = url.match(/\/assets\/([^/?]+)\/content/)?.[1] ?? "";
    if (url.includes("live=1")) return route.continue();
    const inputs = await page
      .evaluate(() =>
        (window as unknown as { __chimera?: { graph(): { nodes: Array<{ type: string; data: { assetId?: string } }> } } }).__chimera
          ?.graph()
          .nodes.filter((n) => n.type === "image-input")
          .map((n) => n.data.assetId),
      )
      .catch(() => []);
    if ((inputs ?? []).includes(id)) return route.continue();
    await route.fulfill({ status: 200, contentType: "image/webp", body: readFileSync(join(LIVE_FUSIONS, `${fusionFor()}.webp`)) });
  });
}
