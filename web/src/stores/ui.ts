import { create } from "zustand";

type Theme = "dark" | "light";

function initialTheme(): Theme {
  const saved = localStorage.getItem("orbit-theme");
  if (saved === "dark" || saved === "light") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

type Toast = { id: number; message: string; undo?: () => void };

type UiState = {
  theme: Theme;
  sidebar: boolean;
  palette: boolean;
  help: boolean;
  toasts: Toast[];
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
  toggleSidebar: () => void;
  setPalette: (open: boolean) => void;
  setHelp: (open: boolean) => void;
  pushToast: (message: string, undo?: () => void) => void;
  dismissToast: (id: number) => void;
};

export const useUi = create<UiState>((set, get) => ({
  theme: initialTheme(),
  sidebar: true,
  palette: false,
  help: false,
  toasts: [],
  setTheme: (theme) => {
    localStorage.setItem("orbit-theme", theme);
    document.documentElement.dataset.theme = theme;
    set({ theme });
  },
  toggleTheme: () => get().setTheme(get().theme === "dark" ? "light" : "dark"),
  toggleSidebar: () => set({ sidebar: !get().sidebar }),
  setPalette: (palette) => set({ palette }),
  setHelp: (help) => set({ help }),
  pushToast: (message, undo) => {
    const id = Date.now();
    set({ toasts: [...get().toasts, { id, message, undo }] });
    window.setTimeout(() => get().dismissToast(id), 5000);
  },
  dismissToast: (id) => set({ toasts: get().toasts.filter((toast) => toast.id !== id) }),
}));
