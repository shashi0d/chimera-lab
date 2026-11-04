import { absoluteUrl, baseHeaders, parseError, request } from "../api/client";
import type { GraphDoc } from "../graph/types";
import { isTutorialId, tutorialLab } from "../tutorial/sandbox";

/** The Lab API (/evo/lab): versions of a creature, edit jobs, cards, workspaces, saved chimeras. */

export type Operation = "fusion" | "revise" | "paint" | "sketch";

export interface LabVersion {
  id: string;
  parentId: string | null;
  runId: string | null;
  creatureId: string | null;
  operation: Operation;
  instruction: string;
  imageUrl: string;
  createdAt: string;
  isFinal: boolean;
  title: string | null;
  style?: string | null;
  /** The creature's basic info, written when the image was generated (its title is the profile's name). */
  profile?: CreatureProfile | null;
  /** The animal card, once made (one per image, on demand). */
  card?: AnimalCard | null;
  /** Saved to the chimeras page (its card is made in the background). */
  saved?: boolean;
  savedAt?: string | null;
  /** Shared to the Garden: everyone can see it there. */
  shared?: boolean;
  sharedAt?: string | null;
  /** In the Garden: this visitor's own creature. */
  mine?: boolean;
  /** The workspace it was made in. */
  workspaceId?: string | null;
}

export interface WorkspaceInfo {
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
  revision?: number;
  imageCount?: number;
  /** Up to four of its newest images (the home page's tile). */
  thumbnails?: string[];
}

/** A generated creature's field-guide entry, written by the vision model from the image and how it was made. */
export interface CreatureProfile {
  name: string;
  length: string;
  weight: string;
  habitat: string;
  explorers_notes: string;
  /** Its defining feature as one word ("SCALES"). */
  trait: string;
  summary: string;
  accent_color: string;
  /** The model's reasoning for this entry. */
  reasoning: string;
}

/** The animal card: the profile plus four more angles of the creature (made in the background). */
export interface AnimalCard {
  status: "running" | "ready" | "failed";
  profile: CreatureProfile | null;
  angles: { view: string; url: string }[];
  error: string | null;
}

export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "interrupted";

export interface LabJob {
  id: string;
  operation: "revise" | "paint" | "sketch";
  status: JobStatus;
  stage: string;
  parentId: string;
  instruction: string;
  createdAt: string;
  updatedAt: string;
  result: LabVersion | null;
  error: string | null;
}

export interface LabLimits {
  used: number;
  /** Null when the server has no limits. */
  limit: number | null;
  totalUsed: number;
  totalLimit: number | null;
  resetsAt: string;
}

const enc = encodeURIComponent;
const json = (body: unknown) => ({ headers: baseHeaders({ "Content-Type": "application/json" }), body: JSON.stringify(body) });

export const labApi = {
  async versionFromRun(runId: string, workspaceId?: string | null): Promise<LabVersion> {
    if (isTutorialId(runId)) return tutorialLab.versionFromRun();
    return (await request<LabVersion>("/evo/lab/versions/from-run", { method: "POST", ...json({ runId, workspaceId }) })).data;
  },
  async sketch(versionId: string, drawing: Blob, instruction: string): Promise<LabJob> {
    if (isTutorialId(versionId)) tutorialLab.onlyLook();
    const form = new FormData();
    form.append("sketch", drawing, "sketch.png");
    if (instruction) form.append("instruction", instruction);
    return (await request<LabJob>(`/evo/lab/versions/${enc(versionId)}/sketch`, { method: "POST", headers: baseHeaders(), body: form })).data;
  },
  async deleteVersion(versionId: string): Promise<void> {
    if (isTutorialId(versionId)) tutorialLab.onlyLook();
    await request(`/evo/lab/versions/${enc(versionId)}`, { method: "DELETE", headers: baseHeaders() });
  },
  async setSaved(versionId: string, saved: boolean): Promise<LabVersion> {
    if (isTutorialId(versionId)) return tutorialLab.setSaved(saved);
    return (await request<LabVersion>(`/evo/lab/versions/${enc(versionId)}/saved`, { method: "PUT", ...json({ saved }) })).data;
  },
  /** Share to the Garden (or take it back). Sharing also saves it and makes its card. */
  async setShared(versionId: string, shared: boolean): Promise<LabVersion> {
    if (isTutorialId(versionId)) tutorialLab.onlyLook();
    return (await request<LabVersion>(`/evo/lab/versions/${enc(versionId)}/garden`, { method: "PUT", ...json({ shared }) })).data;
  },
  /** Every creature shared to the Garden, by anyone (newest first). */
  async garden(): Promise<LabVersion[]> {
    return (await request<{ garden: LabVersion[] }>("/evo/garden", { headers: baseHeaders(), timeoutMs: 15000 })).data.garden;
  },
  async chimeras(): Promise<LabVersion[]> {
    return tutorialLab.withChimeras((await request<{ chimeras: LabVersion[] }>("/evo/lab/chimeras", { headers: baseHeaders(), timeoutMs: 15000 })).data.chimeras);
  },
  async editProfile(versionId: string, fields: Partial<Pick<CreatureProfile, "name" | "length" | "weight" | "habitat" | "explorers_notes">>): Promise<LabVersion> {
    if (isTutorialId(versionId)) tutorialLab.onlyLook();
    return (await request<LabVersion>(`/evo/lab/versions/${enc(versionId)}/profile`, { method: "PUT", ...json(fields) })).data;
  },
  async workspaces(): Promise<WorkspaceInfo[]> {
    return (await request<{ workspaces: WorkspaceInfo[] }>("/evo/lab/workspaces", { headers: baseHeaders(), timeoutMs: 15000 })).data.workspaces;
  },
  async createWorkspace(name: string): Promise<WorkspaceInfo> {
    return (await request<WorkspaceInfo>("/evo/lab/workspaces", { method: "POST", ...json({ name }) })).data;
  },
  async loadWorkspace(id: string): Promise<WorkspaceInfo & { graph: GraphDoc | null }> {
    if (isTutorialId(id)) return tutorialLab.loadWorkspace();
    return (await request<WorkspaceInfo & { graph: GraphDoc | null }>(`/evo/lab/workspaces/${enc(id)}`, { headers: baseHeaders(), timeoutMs: 15000 })).data;
  },
  async saveWorkspace(id: string, body: { graph?: GraphDoc; name?: string }): Promise<WorkspaceInfo> {
    if (isTutorialId(id)) return tutorialLab.saveWorkspace();
    return (await request<WorkspaceInfo>(`/evo/lab/workspaces/${enc(id)}`, { method: "PUT", ...json(body), timeoutMs: 15000 })).data;
  },
  async deleteWorkspace(id: string): Promise<{ imagesDeleted: number }> {
    if (isTutorialId(id)) return { imagesDeleted: 0 };
    return (await request<{ imagesDeleted: number }>(`/evo/lab/workspaces/${enc(id)}`, { method: "DELETE", headers: baseHeaders(), timeoutMs: 60000 })).data;
  },
  async workspaceImages(id: string): Promise<LabVersion[]> {
    if (isTutorialId(id)) return [];
    return (await request<{ images: LabVersion[] }>(`/evo/lab/workspaces/${enc(id)}/images`, { headers: baseHeaders() })).data.images;
  },
  async versions(): Promise<LabVersion[]> {
    return (await request<{ versions: LabVersion[] }>("/evo/lab/versions", { headers: baseHeaders() })).data.versions;
  },
  async revise(versionId: string, instruction: string): Promise<LabJob> {
    if (isTutorialId(versionId)) tutorialLab.onlyLook();
    return (await request<LabJob>(`/evo/lab/versions/${enc(versionId)}/revise`, { method: "POST", ...json({ instruction }) })).data;
  },
  async paint(versionId: string, mask: Blob, instruction: string): Promise<LabJob> {
    if (isTutorialId(versionId)) tutorialLab.onlyLook();
    const form = new FormData();
    form.append("mask", mask, "mask.png");
    form.append("instruction", instruction);
    return (await request<LabJob>(`/evo/lab/versions/${enc(versionId)}/paint`, { method: "POST", headers: baseHeaders(), body: form })).data;
  },
  async jobs(): Promise<LabJob[]> {
    return (await request<{ jobs: LabJob[] }>("/evo/lab/jobs", { headers: baseHeaders(), timeoutMs: 15000 })).data.jobs;
  },
  async limits(): Promise<LabLimits> {
    return (await request<LabLimits>("/evo/lab/limits", { headers: baseHeaders(), timeoutMs: 10000 })).data;
  },
  async setFinal(versionId: string, isFinal: boolean): Promise<LabVersion> {
    if (isTutorialId(versionId)) tutorialLab.onlyLook();
    return (await request<LabVersion>(`/evo/lab/versions/${enc(versionId)}/final`, { method: "PUT", ...json({ isFinal }) })).data;
  },
  /** Make the image's card (or get the one it already has: one card per image). */
  async card(versionId: string): Promise<AnimalCard> {
    if (isTutorialId(versionId)) return tutorialLab.card();
    return (await request<AnimalCard>(`/evo/lab/versions/${enc(versionId)}/card`, { method: "POST", headers: baseHeaders(), timeoutMs: 30000 })).data;
  },
  async savedCard(versionId: string): Promise<AnimalCard | null> {
    if (isTutorialId(versionId)) return tutorialLab.savedCard();
    return (await request<{ card: AnimalCard | null }>(`/evo/lab/versions/${enc(versionId)}/card`, { headers: baseHeaders() })).data.card;
  },
  async download(versionId: string): Promise<Blob> {
    if (isTutorialId(versionId)) return tutorialLab.download();
    const res = await fetch(absoluteUrl(`/evo/lab/versions/${enc(versionId)}/download`), { headers: baseHeaders() });
    if (!res.ok) throw await parseError(res);
    return res.blob();
  },
};
