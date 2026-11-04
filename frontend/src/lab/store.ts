import { create } from "zustand";
import { toAppError } from "../api/errors";
import { presentError } from "../api/errorMessages";
import { useGraph } from "../graph/store";
import { maskKey, sketchKey, type EditConfig, type EditData } from "../nodes/edit/types";
import { useWorkspaces } from "../persistence/workspaces";
import type { VersionData } from "../nodes/version/types";
import { getBlob } from "../persistence/blobStore";
import { toast } from "../ui/toastStore";
import { labApi, type LabJob, type LabLimits, type LabVersion } from "./api";
import { addVersionNode, editNodesWithJobs, findRunVersionNode, findVersionNode, parentVersionOf } from "./graph";

/**
 * Lab state outside the canvas document: edit jobs (polled while any runs), the daily lab budget, and the
 * actions that turn server results into cards on the canvas. Jobs run on the server, so a reload or another tab
 * picks them up again from GET /evo/lab/jobs.
 */

const POLL_MS = 2000;
const ACTIVE = new Set(["queued", "running"]);

interface LabState {
  jobs: Record<string, LabJob>;
  limits: LabLimits | null;
  starting: Record<string, boolean>;
  refreshLimits(): Promise<void>;
}

export const useLab = create<LabState>()((set) => ({
  jobs: {},
  limits: null,
  starting: {},
  async refreshLimits() {
    try {
      set({ limits: await labApi.limits() });
    } catch {
      /* shown when available */
    }
  },
}));

function message(e: unknown): string {
  const p = presentError(toAppError(e));
  return p.fix ? `${p.title} ${p.fix}` : p.title;
}

function updateEdit(nodeId: string, fn: (d: EditData) => EditData): void {
  useGraph.getState().updateNodeData<EditData>(nodeId, fn);
}

// ------------------------------------------------------------------ jobs → cards

/** A finished job's image becomes a card after its edit card (once, also after a reload). */
function applyJob(job: LabJob): void {
  const edit = editNodesWithJobs().find((n) => (n.data.jobIds ?? []).includes(job.id));
  if (!edit) return;
  if (job.status === "succeeded" && job.result && !findVersionNode(job.result.id)) {
    addVersionNode(edit.id, { version: job.result, runId: null, error: null });
  }
  if (edit.data.activeJobId === job.id && !ACTIVE.has(job.status)) {
    const failed = job.status === "failed" || job.status === "interrupted";
    updateEdit(edit.id, (d) => ({ ...d, activeJobId: null, error: failed ? job.error ?? "The edit failed." : null }));
    void useLab.getState().refreshLimits();
  }
}

let timer: ReturnType<typeof setTimeout> | null = null;
let polling = false;

function needsPolling(): boolean {
  const jobs = useLab.getState().jobs;
  return editNodesWithJobs().some((n) => n.data.activeJobId && (!jobs[n.data.activeJobId] || ACTIVE.has(jobs[n.data.activeJobId]!.status)));
}

async function pollOnce(): Promise<void> {
  try {
    const list = await labApi.jobs();
    useLab.setState((s) => ({ jobs: { ...s.jobs, ...Object.fromEntries(list.map((j) => [j.id, j])) } }));
    list.forEach(applyJob);
  } catch {
    /* keep polling through a network drop */
  }
}

/** Follow edit jobs until none is running (call after starting one, and once when the Lab opens). */
export function followJobs(): void {
  if (polling) return;
  polling = true;
  const tick = async () => {
    await pollOnce();
    if (needsPolling()) timer = setTimeout(() => void tick(), POLL_MS);
    else {
      polling = false;
      timer = null;
    }
  };
  void tick();
}

export function stopFollowingJobs(): void {
  if (timer) clearTimeout(timer);
  timer = null;
  polling = false;
}

// ------------------------------------------------------------------ actions

/** Generate: send this card's change for its connected image. Each success adds an image card after it. */
export async function generateEdit(nodeId: string): Promise<void> {
  const node = useGraph.getState().nodes.find((n) => n.id === nodeId);
  if (!node || useLab.getState().starting[nodeId]) return;
  const config = node.config as EditConfig;
  const parent = parentVersionOf(nodeId)?.version;
  if (!parent) {
    updateEdit(nodeId, (d) => ({ ...d, error: "Connect a finished image to edit." }));
    return;
  }
  useLab.setState((s) => ({ starting: { ...s.starting, [nodeId]: true } }));
  updateEdit(nodeId, (d) => ({ ...d, error: null }));
  try {
    let job: LabJob;
    if (config.operation === "paint") {
      const mask = await getBlob(maskKey(nodeId));
      if (!mask) {
        updateEdit(nodeId, (d) => ({ ...d, hasMask: false, error: "Paint the area to change." }));
        return;
      }
      job = await labApi.paint(parent.id, mask, config.instruction.trim());
    } else if (config.operation === "sketch") {
      const drawing = await getBlob(sketchKey(nodeId));
      if (!drawing) {
        updateEdit(nodeId, (d) => ({ ...d, hasSketch: false, error: "Draw on the image first." }));
        return;
      }
      job = await labApi.sketch(parent.id, drawing, config.instruction.trim());
    } else job = await labApi.revise(parent.id, config.instruction.trim());
    useLab.setState((s) => ({ jobs: { ...s.jobs, [job.id]: job } }));
    updateEdit(nodeId, (d) => ({ ...d, jobIds: [...(d.jobIds ?? []), job.id], activeJobId: job.id, error: null }));
    void useLab.getState().refreshLimits();
    followJobs();
  } catch (e) {
    updateEdit(nodeId, (d) => ({ ...d, error: message(e) }));
  } finally {
    useLab.setState((s) => ({ starting: { ...s.starting, [nodeId]: false } }));
  }
}

const fetchingRuns = new Set<string>();

/** The Fusion run's first image card: a waiting card as the run starts, filled when it finishes. */
export function ensureRunVersion(fusionNodeId: string, runId: string, finished: boolean): void {
  let node = findRunVersionNode(runId);
  if (!node) {
    addVersionNode(fusionNodeId, { version: null, runId, error: null });
    node = findRunVersionNode(runId);
  }
  if (!finished || !node || (node.data as VersionData).version || fetchingRuns.has(runId)) return;
  fetchingRuns.add(runId);
  const id = node.id;
  void labApi
    .versionFromRun(runId, useWorkspaces.getState().currentId)
    .then((version) => useGraph.getState().updateNodeData<VersionData>(id, (d) => ({ ...d, version, error: null })))
    .catch((e) => useGraph.getState().updateNodeData<VersionData>(id, (d) => ({ ...d, error: message(e) })))
    .finally(() => fetchingRuns.delete(runId));
}

/** Save a creature to the chimeras page (at once); its animal card is made in the background. */
export async function saveCreature(version: LabVersion, saved = true): Promise<void> {
  try {
    updateVersion(await labApi.setSaved(version.id, saved));
    if (saved) toast.success(`Saved ${version.title ?? "the creature"}. Its card is being drawn.`);
  } catch (e) {
    toast.error(message(e));
  }
}

/** Keep a card's copy of a version in step after a change on the server (final mark, publish). */
export function updateVersion(version: LabVersion): void {
  for (const n of useGraph.getState().nodes) {
    if (n.type === "version" && (n.data as VersionData).version?.id === version.id) {
      useGraph.getState().updateNodeData<VersionData>(n.id, (d) => ({ ...d, version }));
    }
  }
}

export async function downloadVersion(version: LabVersion, label: string): Promise<void> {
  try {
    const blob = await labApi.download(version.id);
    const url = URL.createObjectURL(blob);
    const ext = blob.type === "image/png" ? "png" : blob.type === "image/jpeg" ? "jpg" : "webp";
    const a = document.createElement("a");
    a.href = url;
    a.download = `chimera-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.${ext}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (e) {
    toast.error(message(e));
  }
}
