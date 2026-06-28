/**
 * Agent OS V6.0 — Auth helpers (SSR-safe)
 *
 * - JWT token / tenant / user storage via localStorage (browser only).
 * - Simple JWT payload decoder (no verify; that's the backend's job).
 * - AuthContext and AuthProvider for React tree.
 */

"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";

// ---------- storage keys ----------

const TOKEN_KEY = "auth_token";
const TENANT_KEY = "tenant_id";
const USER_KEY = "user_id";

// ---------- browser-safe accessors ----------

const store = {
  get: (key: string): string | null => {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(key);
  },
  set: (key: string, val: string) => {
    if (typeof window === "undefined") return;
    localStorage.setItem(key, val);
  },
  remove: (key: string) => {
    if (typeof window === "undefined") return;
    localStorage.removeItem(key);
  },
};

// ---------- token helpers ----------

export function getToken(): string | null {
  return store.get(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) store.set(TOKEN_KEY, token);
  else store.remove(TOKEN_KEY);
}

export function getTenantId(): string | null {
  return store.get(TENANT_KEY);
}

export function setTenantId(tid: string | null): void {
  if (tid) store.set(TENANT_KEY, tid);
  else store.remove(TENANT_KEY);
}

export function getUserId(): string | null {
  return store.get(USER_KEY);
}

export function setUserId(uid: string | null): void {
  if (uid) store.set(USER_KEY, uid);
  else store.remove(USER_KEY);
}

/** Decode a JWT *payload* without verification. Returns null on failure. */
export function decodeJwtPayload(
  token: string,
): Record<string, unknown> | null {
  try {
    const base64 = token.split(".")[1];
    if (!base64) return null;
    const json = atob(base64.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json);
  } catch {
    return null;
  }
}

// ---------- auth context (React) ----------

export interface AuthUser {
  user_id: string;
  tenant_id: string;
  username: string;
  roles: string[];
}

export interface AuthState {
  token: string | null;
  user: AuthUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (token: string, user: AuthUser) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(null);
  const [user, setUserState] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Hydrate from localStorage on mount
  useEffect(() => {
    const t = getToken();
    if (t) {
      const payload = decodeJwtPayload(t);
      if (payload) {
        setTokenState(t);
        setUserState({
          user_id: (payload.sub as string) ?? "",
          tenant_id: (payload.tenant_id as string) ?? "",
          username: (payload.username as string) ?? "",
          roles: (payload.roles as string[]) ?? [],
        });
      }
    }
    setIsLoading(false);
  }, []);

  const login = useCallback((t: string, u: AuthUser) => {
    setToken(t);
    setTenantId(u.tenant_id);
    setUserId(u.user_id);
    setTokenState(t);
    setUserState(u);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setTenantId(null);
    setUserId(null);
    setTokenState(null);
    setUserState(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        isLoading,
        isAuthenticated: !!token && !!user,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
