/**
 * Agent OS V6.0 - Auth compatibility layer (Zustand-backed)
 *
 * Re-exports from the Zustand authStore while keeping the existing
 * React Context API (`useAuth`, `AuthProvider`) for zero-friction
 * migration of existing components.
 */

"use client";

import { createContext, useContext, useEffect, type ReactNode } from "react";
import { useAuthStore, type AuthUser } from "@/stores/authStore";

// Re-export token helpers
export { useAuthStore } from "@/stores/authStore";
export type { AuthUser } from "@/stores/authStore";

// ---------------------------------------------------------------------------
// Legacy-compatible React Context (wraps Zustand)
// ---------------------------------------------------------------------------

interface AuthCtx {
  token: string | null;
  user: AuthUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (token: string, user: AuthUser) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const store = useAuthStore();

  // Hydrate on mount
  useEffect(() => {
    store.hydrate();
  }, []);

  const ctx: AuthCtx = {
    token: store.token,
    user: store.user,
    isLoading: store.isLoading,
    isAuthenticated: !!store.token && !!store.user,
    login: store.login,
    logout: store.logout,
  };

  return <AuthContext.Provider value={ctx}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthCtx {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
