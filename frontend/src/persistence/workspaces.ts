import { create } from "zustand";
import { labApi, type WorkspaceInfo } from "../lab/api";

/**
 * The user's workspaces (named canvases on the server). The open one is remembered per user on this device; the
 * Lab loads its canvas and saves to it (persistence/autosave).
 */

const lastKey = (userId: string) => `chimera.workspace.${userId}`;

interface WorkspacesState {
  userId: string | null;
  list: WorkspaceInfo[];
  currentId: string | null;
  loaded: boolean;
  /** Read the list; open the remembered workspace, else the most recent one. */
  init(userId: string, preferred?: string | null): Promise<void>;
  refresh(): Promise<void>;
  open(id: string): void;
  create(name: string): Promise<WorkspaceInfo>;
  rename(id: string, name: string): Promise<void>;
  remove(id: string): Promise<number>;
  reset(): void;
}

function remember(userId: string | null, id: string | null): void {
  if (!userId) return;
  try {
    if (id) localStorage.setItem(lastKey(userId), id);
    else localStorage.removeItem(lastKey(userId));
  } catch {
    // private mode: the choice lasts for this page only
  }
}

export const useWorkspaces = create<WorkspacesState>()((set, get) => ({
  userId: null,
  list: [],
  currentId: null,
  loaded: false,

  async init(userId, preferred) {
    set({ userId, loaded: false });
    let list: WorkspaceInfo[] = [];
    try {
      list = await labApi.workspaces();
    } catch {
      list = [];
    }
    let stored: string | null = null;
    try {
      stored = localStorage.getItem(lastKey(userId));
    } catch {
      stored = null;
    }
    const currentId = list.find((w) => w.id === preferred)?.id ?? list.find((w) => w.id === stored)?.id ?? list[0]?.id ?? "main";
    remember(userId, currentId);
    set({ list, currentId, loaded: true });
  },

  async refresh() {
    try {
      set({ list: await labApi.workspaces() });
    } catch {
      // keep the list we have
    }
  },

  open(id) {
    if (id === get().currentId) return;
    remember(get().userId, id);
    set({ currentId: id });
  },

  async create(name) {
    const ws = await labApi.createWorkspace(name);
    set((s) => ({ list: [ws, ...s.list] }));
    return ws;
  },

  async rename(id, name) {
    const ws = await labApi.saveWorkspace(id, { name });
    set((s) => ({ list: s.list.map((w) => (w.id === id ? { ...w, name: ws.name, updatedAt: ws.updatedAt } : w)) }));
  },

  async remove(id) {
    const { imagesDeleted } = await labApi.deleteWorkspace(id);
    const rest = get().list.filter((w) => w.id !== id);
    if (get().currentId === id) {
      const next = rest[0] ?? (await labApi.createWorkspace("My workspace"));
      if (!rest.length) rest.push(next);
      remember(get().userId, next.id);
      set({ list: rest, currentId: next.id });
    } else set({ list: rest });
    return imagesDeleted;
  },

  reset() {
    set({ userId: null, list: [], currentId: null, loaded: false });
  },
}));

export function currentWorkspace(): WorkspaceInfo | undefined {
  const s = useWorkspaces.getState();
  return s.list.find((w) => w.id === s.currentId);
}
