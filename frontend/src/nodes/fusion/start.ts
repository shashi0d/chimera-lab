import { create } from "zustand";
import { presentError } from "../../api/errorMessages";
import { ApiRequestError, toAppError, type AppError } from "../../api/errors";
import { toast } from "../../ui/toastStore";
import { navigate } from "../../app/route";
import { copy } from "../../copy";
import { useLimits } from "../../evo/data";
import { evo } from "../../evo/index";
import { useEvoRuns } from "../../evo/runs";
import type { IdentifyChoice, Mode, Parent, RunAccepted, Slot, StartInput } from "../../evo/types";
import { upstreamNode } from "../../graph/queries";
import { useGraph } from "../../graph/store";
import { getBlob } from "../../persistence/blobStore";
import type { ImageInputData } from "../image-input/types";
import { ensureRunVersion } from "../../lab/store";
import type { VersionData } from "../version/types";
import { useWorkspaces } from "../../persistence/workspaces";
import { cleanName, readMode, readStyle, type FusionData } from "./types";

/** An identify question from the POST response, waiting for the user (no run exists yet). */
export interface PendingIdentify {
  nodeId: string;
  mode: Mode;
  choice: IdentifyChoice["choice"];
  identified: IdentifyChoice["identified"];
  /** Names typed for slots that had no photo, re-sent with the confirmed names. */
  typed: { sire: string | null; dam: string | null };
}

interface StartState {
  starting: Record<string, boolean>;
  errors: Record<string, AppError | undefined>;
  identify: PendingIdentify | null;
  clearError(nodeId: string): void;
  dismissIdentify(): void;
}

export const useFusionStart = create<StartState>()((set) => ({
  starting: {},
  errors: {},
  identify: null,
  clearError(nodeId) {
    set((s) => ({ errors: { ...s.errors, [nodeId]: undefined } }));
  },
  dismissIdentify() {
    set({ identify: null });
  },
}));

const SLOT_PORT: Record<Slot, "a" | "b"> = { sire: "a", dam: "b" };

function setStarting(nodeId: string, v: boolean) {
  useFusionStart.setState((s) => ({ starting: { ...s.starting, [nodeId]: v } }));
}
function setError(nodeId: string, err: AppError | undefined) {
  useFusionStart.setState((s) => ({ errors: { ...s.errors, [nodeId]: err } }));
}

/** Mark (or clear) the photo a refusal points at, so the canvas shows which one to replace. */
export function flagSlot(nodeId: string, slot: Slot | null, message: string | null): void {
  const g = useGraph.getState();
  for (const s of ["sire", "dam"] as const) {
    const up = upstreamNode(g, nodeId, SLOT_PORT[s]);
    if (!up || up.type !== "image-input") continue;
    const flagged = slot === s ? message : null;
    if ((up.data as ImageInputData).flagged !== flagged) g.updateNodeData<ImageInputData>(up.id, (d) => ({ ...d, flagged }));
  }
}

function recordIdentified(nodeId: string, parents: { sire: Parent | null; dam: Parent | null }): void {
  const g = useGraph.getState();
  for (const s of ["sire", "dam"] as const) {
    const p = parents[s];
    const up = upstreamNode(g, nodeId, SLOT_PORT[s]);
    if (!p || !up || up.type !== "image-input" || p.source !== "image") continue;
    g.updateNodeData<ImageInputData>(up.id, (d) => ({ ...d, species: p.commonName }));
  }
}

function accepted(nodeId: string, res: RunAccepted): void {
  const g = useGraph.getState();
  g.updateNodeData<FusionData>(nodeId, (d) => ({
    ...d,
    activeRunId: res.runId,
    runIds: [...(d.runIds ?? []).filter((id) => id !== res.runId), res.runId],
    stale: false,
  }));
  recordIdentified(nodeId, res);
  flagSlot(nodeId, null, null);
  ensureRunVersion(nodeId, res.runId, false);
  useEvoRuns.getState().attach(res.runId, res);
  void useLimits.getState().refresh();
  navigate({ view: "lab", runId: res.runId, workspaceId: useWorkspaces.getState().currentId });
}

function handleError(nodeId: string, e: unknown): void {
  const err = toAppError(e);
  setError(nodeId, err);
  // On a phone the canvas is zoomed out, so the node's error block is small: say it in a toast too.
  if (typeof window !== "undefined" && window.matchMedia?.("(max-width: 1023px)").matches) {
    const p = presentError(err);
    toast.error(`${p.title}${p.fix ? ` ${p.fix}` : ""}`);
  }
  const slot = (err.details as { slot?: Slot } | undefined)?.slot ?? null;
  if (err.code === "HUMAN_DETECTED") flagSlot(nodeId, slot, copy.nodes.imageInput.highlightHuman);
  else if (["NOT_AN_ANIMAL", "UNSUPPORTED_FILE", "FILE_TOO_LARGE", "IMAGE_CORRUPT"].includes(err.code)) flagSlot(nodeId, slot, copy.nodes.imageInput.highlight);
  if (err.code === "CAP_REACHED") {
    useLimits.getState().setCapError(err);
    void useLimits.getState().refresh();
  }
}

async function post(nodeId: string, input: StartInput, typed: PendingIdentify["typed"]): Promise<void> {
  if (useFusionStart.getState().starting[nodeId]) return; // double-click guard
  setStarting(nodeId, true);
  setError(nodeId, undefined);
  try {
    const res = await evo().startRun(input);
    if (res.kind === "identify") {
      recordIdentified(nodeId, res.identified);
      useFusionStart.setState({ identify: { nodeId, mode: input.mode, choice: res.choice, identified: res.identified, typed } });
    } else accepted(nodeId, res);
  } catch (e) {
    handleError(nodeId, e);
  } finally {
    setStarting(nodeId, false);
  }
}

/**
 * What each slot sends: an earlier generated creature (its version id), a photo, or the typed name when nothing is
 * connected. Photos and earlier creatures go to the image model as references. Null when a local photo is missing
 * or an image card has not finished (the error is shown on the node).
 */
async function collectInput(nodeId: string): Promise<{ input: StartInput; typed: PendingIdentify["typed"] } | null> {
  const g = useGraph.getState();
  const node = g.nodes.find((n) => n.id === nodeId);
  if (!node) return null;
  const names = (node.data as FusionData).names ?? { a: "", b: "" };
  const input: StartInput = { mode: readMode(node.config), style: readStyle(node.config) };
  const workspaceId = useWorkspaces.getState().currentId;
  if (workspaceId) input.workspaceId = workspaceId;
  const typed: PendingIdentify["typed"] = { sire: null, dam: null };
  for (const s of ["sire", "dam"] as const) {
    const port = SLOT_PORT[s];
    const up = upstreamNode(g, nodeId, port);
    if (up?.type === "version") {
      const version = (up.data as VersionData).version;
      if (!version) {
        handleError(nodeId, new ApiRequestError({ code: "VALIDATION_FAILED", message: copy.nodes.fusion.imagePending, retryable: false, details: { slot: s } }));
        return null;
      }
      Object.assign(input, s === "sire" ? { sireVersionId: version.id } : { damVersionId: version.id });
      continue;
    }
    const key = (up?.data as ImageInputData | undefined)?.blobKey;
    const blob = key ? await getBlob(key) : undefined;
    if (up && !blob) {
      handleError(nodeId, new ApiRequestError({ code: "IMAGE_CORRUPT", message: "Local copy missing.", retryable: false, details: { slot: s } }));
      return null;
    }
    const name = blob ? null : cleanName(names[port]);
    if (s === "sire") Object.assign(input, blob ? { sireImage: blob } : { sireName: name });
    else Object.assign(input, blob ? { damImage: blob } : { damName: name });
    typed[s] = name;
  }
  return { input, typed };
}

/** Make creature: each slot sends its photo, earlier creature, or typed name. */
export async function startFusion(nodeId: string): Promise<void> {
  const collected = await collectInput(nodeId);
  if (collected) await post(nodeId, collected.input, collected.typed);
}

/** Identify confirmation: post again with the confirmed names, and the photos again (they go to the image model). */
export async function confirmIdentify(answer: string): Promise<void> {
  const pending = useFusionStart.getState().identify;
  const name = cleanName(answer);
  if (!pending || !name) return;
  useFusionStart.setState({ identify: null });
  const other: Slot = pending.choice.slot === "sire" ? "dam" : "sire";
  const otherName = pending.identified[other]?.commonName ?? pending.typed[other];
  const collected = await collectInput(pending.nodeId);
  const base: StartInput = collected?.input ?? { mode: pending.mode };
  const names = pending.choice.slot === "sire" ? { sireName: name, damName: otherName ?? null } : { sireName: otherName ?? null, damName: name };
  // A slot fed by an earlier creature keeps its version id; its name comes from that image.
  const input: StartInput = { ...base, mode: pending.mode, ...names };
  if (input.sireVersionId) input.sireName = null;
  if (input.damVersionId) input.damName = null;
  await post(pending.nodeId, input, pending.typed);
}
