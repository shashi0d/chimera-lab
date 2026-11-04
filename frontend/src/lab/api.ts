import { absoluteUrl, baseHeaders, parseError, request } from "../api/client";
import type { GraphDoc } from "../graph/types";

/** The Lab API (/evo/lab): versions of a creature, edit jobs, review, collaborator, workspace, publishing. */

export type Operation = "fusion" | "revise" | "paint";

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
  publicationId: string | null;
  title: string | null;
  style?: string | null;
  /** The creature's basic info, written when the image was generated (its title is the profile's name). */
  profile?: CreatureProfile | null;
  /** The animal card, once made (one per image, on demand). */
  card?: AnimalCard | null;
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
  operation: "revise" | "paint";
  status: JobStatus;
  stage: string;
  parentId: string;
  instruction: string;
  createdAt: string;
  updatedAt: string;
  result: LabVersion | null;
  error: string | null;
}

export interface Review {
  observation: string;
  suggestions: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface CollaboratorAnswer {
  message: string;
  action: { type: "revise"; instruction: string; reason: string } | null;
  review: Review | null;
  steps: { tool: string; reason: string }[];
}

export interface LabLimits {
  used: number;
  /** Null when the server has no limits. */
  limit: number | null;
  totalUsed: number;
  totalLimit: number | null;
  resetsAt: string;
}

export interface Workspace {
  graph: GraphDoc | null;
  revision: number;
  updatedAt: string | null;
}

const enc = encodeURIComponent;
const json = (body: unknown) => ({ headers: baseHeaders({ "Content-Type": "application/json" }), body: JSON.stringify(body) });

export const labApi = {
  async versionFromRun(runId: string): Promise<LabVersion> {
    return (await request<LabVersion>("/evo/lab/versions/from-run", { method: "POST", ...json({ runId }) })).data;
  },
  async versions(): Promise<LabVersion[]> {
    return (await request<{ versions: LabVersion[] }>("/evo/lab/versions", { headers: baseHeaders() })).data.versions;
  },
  async revise(versionId: string, instruction: string): Promise<LabJob> {
    return (await request<LabJob>(`/evo/lab/versions/${enc(versionId)}/revise`, { method: "POST", ...json({ instruction }) })).data;
  },
  async paint(versionId: string, mask: Blob, instruction: string): Promise<LabJob> {
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
    return (await request<LabVersion>(`/evo/lab/versions/${enc(versionId)}/final`, { method: "PUT", ...json({ isFinal }) })).data;
  },
  async review(versionId: string): Promise<Review> {
    return (await request<Review>(`/evo/lab/versions/${enc(versionId)}/review`, { method: "POST", headers: baseHeaders() })).data;
  },
  /** Make the image's card (or get the one it already has: one card per image). */
  async card(versionId: string): Promise<AnimalCard> {
    return (await request<AnimalCard>(`/evo/lab/versions/${enc(versionId)}/card`, { method: "POST", headers: baseHeaders(), timeoutMs: 30000 })).data;
  },
  async savedCard(versionId: string): Promise<AnimalCard | null> {
    return (await request<{ card: AnimalCard | null }>(`/evo/lab/versions/${enc(versionId)}/card`, { headers: baseHeaders() })).data.card;
  },
  async savedReview(versionId: string): Promise<Review | null> {
    return (await request<{ review: Review | null }>(`/evo/lab/versions/${enc(versionId)}/review`, { headers: baseHeaders() })).data.review;
  },
  async collaborate(versionId: string, messages: ChatMessage[]): Promise<CollaboratorAnswer> {
    return (await request<CollaboratorAnswer>(`/evo/lab/versions/${enc(versionId)}/collaborate`, { method: "POST", ...json({ messages }) })).data;
  },
  async publish(versionId: string, title: string): Promise<LabVersion> {
    return (await request<LabVersion>(`/evo/lab/versions/${enc(versionId)}/publish`, { method: "POST", ...json({ title }) })).data;
  },
  async unpublish(versionId: string): Promise<LabVersion> {
    return (await request<LabVersion>(`/evo/lab/versions/${enc(versionId)}/publish`, { method: "DELETE", headers: baseHeaders() })).data;
  },
  async download(versionId: string): Promise<Blob> {
    const res = await fetch(absoluteUrl(`/evo/lab/versions/${enc(versionId)}/download`), { headers: baseHeaders() });
    if (!res.ok) throw await parseError(res);
    return res.blob();
  },
  async getWorkspace(): Promise<Workspace> {
    return (await request<Workspace>("/evo/lab/workspace", { headers: baseHeaders(), timeoutMs: 15000 })).data;
  },
  async putWorkspace(graph: GraphDoc): Promise<{ revision: number; updatedAt: string }> {
    return (await request<{ revision: number; updatedAt: string }>("/evo/lab/workspace", { method: "PUT", ...json({ graph }), timeoutMs: 15000 })).data;
  },
};
