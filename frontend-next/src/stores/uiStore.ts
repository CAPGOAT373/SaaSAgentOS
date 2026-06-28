import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

type Theme = "light" | "dark";

interface UIState {
  sidebarCollapsed: boolean;
  theme: Theme;
  toggleSidebar: () => void;
  toggleTheme: () => void;
  setTheme: (t: Theme) => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      theme: "light",
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      toggleTheme: () =>
        set((s) => {
          const next: Theme = s.theme === "dark" ? "light" : "dark";
          if (typeof window !== "undefined") {
            document.documentElement.setAttribute("data-theme", next);
          }
          return { theme: next };
        }),
      setTheme: (t: Theme) => {
        if (typeof window !== "undefined") {
          document.documentElement.setAttribute("data-theme", t);
        }
        return { theme: t };
      },
    }),
    {
      name: "agent-os-ui",
      storage: createJSONStorage(() => ({
        getItem: (key) => (typeof window !== "undefined" ? localStorage.getItem(key) : null),
        setItem: (key, value) => { if (typeof window !== "undefined") localStorage.setItem(key, value); },
        removeItem: (key) => { if (typeof window !== "undefined") localStorage.removeItem(key); },
      })),
      partialize: (s) => ({ theme: s.theme, sidebarCollapsed: s.sidebarCollapsed }),
    }
  )
);
