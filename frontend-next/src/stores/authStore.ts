import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

export interface AuthUser {
  user_id: string;
  tenant_id: string;
  username: string;
  roles: string[];
}

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  isLoading: boolean;
  login: (token: string, user: AuthUser) => void;
  logout: () => void;
  hydrate: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isLoading: true,
      login: (token: string, user: AuthUser) => {
        if (typeof window !== "undefined") {
          localStorage.setItem("auth_token", token);
          localStorage.setItem("tenant_id", user.tenant_id);
          localStorage.setItem("user_id", user.user_id);
        }
        set({ token, user, isLoading: false });
      },
      logout: () => {
        if (typeof window !== "undefined") {
          localStorage.removeItem("auth_token");
          localStorage.removeItem("tenant_id");
          localStorage.removeItem("user_id");
        }
        set({ token: null, user: null, isLoading: false });
      },
      hydrate: () => {
        if (typeof window === "undefined") {
          set({ isLoading: false });
          return;
        }
        const token = localStorage.getItem("auth_token");
        if (!token) {
          set({ isLoading: false });
          return;
        }
        try {
          const base64 = token.split(".")[1];
          if (!base64) { set({ isLoading: false }); return; }
          const json = atob(base64.replace(/-/g, "+").replace(/_/g, "/"));
          const payload = JSON.parse(json);
          set({
            token,
            user: {
              user_id: (payload.sub as string) ?? "",
              tenant_id: (payload.tenant_id as string) ?? "",
              username: (payload.username as string) ?? "",
              roles: (payload.roles as string[]) ?? [],
            },
            isLoading: false,
          });
        } catch {
          set({ token, user: null, isLoading: false });
        }
      },
    }),
    {
      name: "agent-os-auth",
      storage: createJSONStorage(() => ({
        getItem: (key) => (typeof window !== "undefined" ? localStorage.getItem(key) : null),
        setItem: (key, value) => { if (typeof window !== "undefined") localStorage.setItem(key, value); },
        removeItem: (key) => { if (typeof window !== "undefined") localStorage.removeItem(key); },
      })),
      partialize: (state) => ({ token: state.token, user: state.user }),
    }
  )
);
