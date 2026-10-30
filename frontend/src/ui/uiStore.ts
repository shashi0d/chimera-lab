import { create } from "zustand";

export type Theme = "light" | "dark";

interface UiState {
  theme: Theme;
  minimap: boolean;
  /** Result node whose "How this was made" panel is open. */
  panel: { nodeId: string } | null;
  shortcutsOpen: boolean;
  /** Test hook: node ids forced to throw on render. */
  crashNodes: string[];
  setTheme(t: Theme): void;
  toggleMinimap(): void;
  openPanel(nodeId: string): void;
  closePanel(): void;
  setShortcutsOpen(v: boolean): void;
}

function initialTheme(): Theme {
  try {
    const t = localStorage.getItem("chimera.theme");
    if (t === "light" || t === "dark") return t;
  } catch {
    /* storage blocked */
  }
  return "light";
}

export const useUi = create<UiState>()((set) => ({
  theme: initialTheme(),
  minimap: false,
  panel: null,
  shortcutsOpen: false,
  crashNodes: [],
  setTheme(theme) {
    try {
      localStorage.setItem("chimera.theme", theme);
    } catch {
      /* ignore */
    }
    document.documentElement.setAttribute("data-theme", theme);
    set({ theme });
  },
  toggleMinimap() {
    set((s) => ({ minimap: !s.minimap }));
  },
  openPanel(nodeId) {
    set({ panel: { nodeId } });
  },
  closePanel() {
    set({ panel: null });
  },
  setShortcutsOpen(v) {
    set({ shortcutsOpen: v });
  },
}));
