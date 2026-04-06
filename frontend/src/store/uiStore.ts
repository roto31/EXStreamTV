import { create } from "zustand";
import { persist } from "zustand/middleware";

interface UIState {
  themeMode: "dark" | "light";
  drawerOpen: boolean;
  welcomeDismissed: boolean;
  toggleTheme: () => void;
  setDrawerOpen: (open: boolean) => void;
  dismissWelcome: () => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      themeMode: "dark",
      drawerOpen: true,
      welcomeDismissed: false,
      toggleTheme: () =>
        set((s) => ({ themeMode: s.themeMode === "dark" ? "light" : "dark" })),
      setDrawerOpen: (open) => set({ drawerOpen: open }),
      dismissWelcome: () => set({ welcomeDismissed: true }),
    }),
    { name: "exstreamtv-ui" }
  )
);
