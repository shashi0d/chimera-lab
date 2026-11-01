import { create } from "zustand";

export type Theme = "light" | "dark";

interface UiState {
  theme: Theme;
  minimap: boolean;
  shortcutsOpen: boolean;
  /** Test hook: node ids forced to throw on render. */
  crashNodes: string[];
  setTheme(t: Theme): void;
  toggleMinimap(): void;
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
  setShortcutsOpen(v) {
    set({ shortcutsOpen: v });
  },
}));
