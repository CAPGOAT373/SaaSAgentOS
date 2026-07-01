/**
 * Agent OS V6.0 — Axios-based API client
 *
 * Unified HTTP client using Axios with:
 *  - Base URL: /api/v1 (proxied via Next.js rewrite to backend)
 *  - Request interceptor: auto-injects JWT Bearer token + X-Tenant-ID
 *  - Response interceptor: unified error handling (401/403/500)
 *
 * Coexists with the fetch-based AgentOSClient (client.ts) and the
 * mock data layer (services/mock/data.ts). No pages are modified.
 */

import axios, { type AxiosInstance, type AxiosError, type InternalAxiosRequestConfig } from "axios";

// ---------------------------------------------------------------------------
// Typed API error — unified contract for React Query / components
// ---------------------------------------------------------------------------

export class AxiosApiError extends Error {
  public readonly status: number;
  public readonly data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = "AxiosApiError";
    this.status = status;
    this.data = data;
  }
}

// ---------------------------------------------------------------------------
// Auth token helpers (SSR-safe)
// ---------------------------------------------------------------------------

function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("auth_token");
}

function getTenantId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("tenant_id");
}

function getUserId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("user_id");
}

// ---------------------------------------------------------------------------
// Axios instance
// ---------------------------------------------------------------------------

const axiosInstance: AxiosInstance = axios.create({
  baseURL: "/api/v1",
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

// ---------------------------------------------------------------------------
// Request interceptor — inject auth
// ---------------------------------------------------------------------------

axiosInstance.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getAuthToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    const tenantId = getTenantId();
    if (tenantId && config.headers) {
      config.headers["X-Tenant-ID"] = tenantId;
    }
    const userId = getUserId();
    if (userId && config.headers) {
      config.headers["X-User-ID"] = userId;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// ---------------------------------------------------------------------------
// Response interceptor — unified error handling
// ---------------------------------------------------------------------------

axiosInstance.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string; error?: { message?: string } }>) => {
    if (error.response) {
      const { status, data } = error.response;
      const message =
        data?.error?.message ?? data?.detail ?? error.message ?? "Request failed";

      if (status === 401) {
        // Token expired or invalid — clear auth state
        if (typeof window !== "undefined") {
          localStorage.removeItem("auth_token");
          localStorage.removeItem("tenant_id");
          localStorage.removeItem("user_id");
        }
      }

      return Promise.reject(new AxiosApiError(message, status, data));
  }

  // Network error
  return Promise.reject(new AxiosApiError(error.message ?? "Network error", 0));
},
);

// ---------------------------------------------------------------------------
// Public API — typed helper
// ---------------------------------------------------------------------------

export interface ApiResponse<T = unknown> {
  data: T;
  status: number;
}

export { axiosInstance };
export default axiosInstance;
