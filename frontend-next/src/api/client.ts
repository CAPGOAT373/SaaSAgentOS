/**
 * Agent OS V6.0 - typed API client
 *
 * A self-contained fetch wrapper (no extra runtime deps) that:
 *  - resolves against a configurable base URL (defaults to same origin so the
 *    Vite dev proxy in vite.config.ts forwards /api -> http://localhost:8000)
 *  - injects Authorization (Bearer), X-Tenant-ID and X-User-ID headers from a
 *    pluggable auth store (default: localStorage-backed, mirrors services/api.ts)
 *  - exposes typed, resource-grouped methods backed by the request models in
 *    schema.ts and the response models in types.ts
 *
 * It coexists with the legacy untyped services/api.ts; new code should import
 * from here. The legacy client can be migrated page-by-page.
 */

import type {
  LoginRequest,
  IdentityCreateRequest,
  TenantCreateRequest,
  AgentRegisterRequest,
  AgentExecuteRequest,
  PluginRegisterRequest,
  PluginInstallRequest,
  WorkflowRunRequest,
  HTTPValidationError,
} from "./schema";
import type {
  AuthLoginResponse,
  AuthRegisterResponse,
  AuthMeResponse,
  HealthResponse,
  AdminHealthAllResponse,
  Tenant,
  Agent,
  AgentExecution,
  AgentReview,
  MarketplaceAgent,
  Plugin,
  BillingBalance,
  BillingReport,
  UsageRecord,
  UsageSummary,
  Workflow,
  WorkflowExecution,
  Trace,
  LatencyMetrics,
  TokenUsageStats,
} from "./types";

const TOKEN_KEY = "auth_token";
const TENANT_KEY = "tenant_id";
const USER_KEY = "user_id";

/** Auth state source. Swap for zustand store / context in the app shell. */
export interface AuthStore {
  getToken(): string | null;
  setToken(token: string | null): void;
  getTenantId(): string | null;
  setTenantId(tenantId: string | null): void;
  getUserId(): string | null;
  setUserId(userId: string | null): void;
}

const localStorageAuthStore: AuthStore = {
  getToken: () => (typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null),
  setToken: (t) => {
    if (typeof window === "undefined") return;
    t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY);
  },
  getTenantId: () => (typeof window !== "undefined" ? localStorage.getItem(TENANT_KEY) : null),
  setTenantId: (t) => {
    if (typeof window === "undefined") return;
    t ? localStorage.setItem(TENANT_KEY, t) : localStorage.removeItem(TENANT_KEY);
  },
  getUserId: () => (typeof window !== "undefined" ? localStorage.getItem(USER_KEY) : null),
  setUserId: (u) => {
    if (typeof window === "undefined") return;
    u ? localStorage.setItem(USER_KEY, u) : localStorage.removeItem(USER_KEY);
  },
};

export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public body: unknown,
    message?: string,
  ) {
    super(message ?? `HTTP ${status} ${statusText}`);
    this.name = "ApiError";
  }

  /** Normalised validation detail (422) or message string. */
  get detail(): string | HTTPValidationError | unknown {
    return this.body;
  }
}

export interface ClientConfig {
 baseUrl?: string;
 authStore?: AuthStore;
}

type Query = Record<string, string | number | boolean | null | undefined>;
type Headers = Record<string, string>;

function buildQuery(params?: Query): string {
  if (!params) return "";
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === null || v === undefined || v === "") continue;
    sp.append(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export class AgentOSClient {
  private baseUrl: string;
  private auth: AuthStore;

  constructor(config: ClientConfig = {}) {
    // Empty base means same-origin, so Vite's /api + /ws proxy applies in dev.
    this.baseUrl = config.baseUrl ?? "";
    this.auth = config.authStore ?? localStorageAuthStore;
  }

  // -- auth store passthroughs -------------------------------------------

  setToken(token: string | null) {
    this.auth.setToken(token);
  }
  getToken() {
    return this.auth.getToken();
  }
  setTenantId(tenantId: string | null) {
    this.auth.setTenantId(tenantId);
  }
  getTenantId() {
    return this.auth.getTenantId();
  }
  setUserId(userId: string | null) {
    this.auth.setUserId(userId);
  }
  getUserId() {
    return this.auth.getUserId();
  }

  // -- core request ------------------------------------------------------

  private baseHeaders(extra?: Headers): Headers {
    const headers: Headers = { "Content-Type": "application/json" };
    const token = this.auth.getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const tenantId = this.auth.getTenantId();
    if (tenantId) headers["X-Tenant-ID"] = tenantId;
    const userId = this.auth.getUserId();
    if (userId) headers["X-User-ID"] = userId;
    return { ...headers, ...extra };
  }

  private async request<T>(
    method: string,
    path: string,
    opts: { query?: Query; body?: unknown; headers?: Headers; signal?: AbortSignal } = {},
  ): Promise<T> {
    const url = `${this.baseUrl}${path}${buildQuery(opts.query)}`;
    const resp = await fetch(url, {
      method,
      headers: this.baseHeaders(opts.headers),
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      signal: opts.signal,
    });
    if (!resp.ok) {
      let body: unknown = undefined;
      try {
        body = await resp.json();
      } catch {
        body = await resp.text().catch(() => undefined);
      }
      throw new ApiError(resp.status, resp.statusText, body);
    }
    if (resp.status === 204) return undefined as T;
    const ct = resp.headers.get("content-type") ?? "";
    if (ct.includes("application/json")) return (await resp.json()) as T;
    return (await resp.text()) as unknown as T;
  }

  // -- System / Health ---------------------------------------------------

  getHealth() {
    return this.request<HealthResponse>("GET", "/health");
  }
  getMetrics() {
    return this.request<string>("GET", "/metrics");
  }
  getAdminHealth() {
    return this.request<AdminHealthAllResponse>("GET", "/api/v1/admin/health/all");
  }

  // -- Auth --------------------------------------------------------------

  async login(body: LoginRequest): Promise<AuthLoginResponse> {
    const res = await this.request<AuthLoginResponse>("POST", "/api/v1/auth/login", { body });
    if (res?.access_token) {
      this.setToken(res.access_token);
      this.setTenantId(res.user?.tenant_id ?? this.getTenantId() ?? "");
      this.setUserId(res.user?.user_id ?? this.getUserId() ?? "");
    }
    return res;
  }

  register(body: IdentityCreateRequest) {
    return this.request<AuthRegisterResponse>("POST", "/api/v1/auth/register", { body });
  }

  getMe() {
    return this.request<AuthMeResponse>("GET", "/api/v1/auth/me");
  }

  // -- Tenant ------------------------------------------------------------

  createTenant(body: TenantCreateRequest) {
    return this.request<Tenant>("POST", "/api/v1/tenant/create", { body });
  }
  getTenant(tenantId: string) {
    return this.request<Tenant>("GET", `/api/v1/tenant/${encodeURIComponent(tenantId)}`);
  }
  listTenants(region?: string) {
    return this.request<Tenant[]>("GET", "/api/v1/tenant", { query: { region } });
  }

  // -- Agent -------------------------------------------------------------

  registerAgent(body: AgentRegisterRequest) {
    return this.request<Agent>("POST", "/api/v1/agent/register", { body });
  }
  getAgent(agentId: string) {
    return this.request<Agent>("GET", `/api/v1/agent/${encodeURIComponent(agentId)}`);
  }
  listAgents(params: { tenantId?: string; limit?: number; offset?: number } = {}) {
    return this.request<Agent[]>("GET", "/api/v1/agent", {
      query: { tenant_id: params.tenantId, limit: params.limit, offset: params.offset },
    });
  }
  executeAgent(body: AgentExecuteRequest) {
    return this.request<AgentExecution>("POST", "/api/v1/agent/execute", { body });
  }
  listAgentExecutions(agentId: string, limit = 50) {
    return this.request<AgentExecution[]>("GET", `/api/v1/agent/${encodeURIComponent(agentId)}/executions`, {
      query: { limit },
    });
  }
  publishAgent(agentId: string) {
    return this.request<Agent>("POST", `/api/v1/agent/${encodeURIComponent(agentId)}/publish`);
  }
  purchaseAgent(agentId: string, headers: { "X-Tenant-ID": string; "X-User-ID": string }) {
    return this.request<Agent>("POST", `/api/v1/agent/${encodeURIComponent(agentId)}/purchase`, { headers });
  }
  reviewAgent(agentId: string, rating: number, comment?: string) {
    return this.request<AgentReview>("POST", `/api/v1/agent/${encodeURIComponent(agentId)}/review`, {
      query: { rating, comment },
    });
  }

  /**
   * Stream agent execution as Server-Sent Events.
   * Yields raw SSE event payloads (already JSON-parsed when possible).
   */
  async *executeAgentStream(body: AgentExecuteRequest, signal?: AbortSignal): AsyncIterable<unknown> {
    const url = `${this.baseUrl}/api/v1/agent/execute/stream`;
    const resp = await fetch(url, {
      method: "POST",
      headers: this.baseHeaders({ Accept: "text/event-stream" }),
      body: JSON.stringify(body),
      signal,
    });
    if (!resp.ok || !resp.body) {
      throw new ApiError(resp.status, resp.statusText, await resp.text().catch(() => undefined));
    }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx: number;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const raw = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          const dataLine = raw.split("\n").find((l) => l.startsWith("data:"));
          if (!dataLine) continue;
          const data = dataLine.slice(5).trim();
          if (!data || data === "[DONE]") continue;
          try {
            yield JSON.parse(data);
          } catch {
            yield data;
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  // -- Marketplace -------------------------------------------------------

  listMarketplace(params: {
    category?: string;
    search?: string;
    sortBy?: string;
    limit?: number;
    offset?: number;
  } = {}) {
    return this.request<MarketplaceAgent[]>("GET", "/api/v1/marketplace/list", {
      query: {
        category: params.category,
        search: params.search,
        sort_by: params.sortBy,
        limit: params.limit,
        offset: params.offset,
      },
    });
  }
  getFeaturedAgents() {
    return this.request<MarketplaceAgent[]>("GET", "/api/v1/marketplace/featured");
  }
  getMarketplaceCategories() {
    return this.request<string[]>("GET", "/api/v1/marketplace/categories");
  }
  listMarketplacePlugins(params: {
    category?: string;
    search?: string;
    sortBy?: string;
    limit?: number;
    offset?: number;
  } = {}) {
    return this.request<Plugin[]>("GET", "/api/v1/marketplace/plugins", {
      query: {
        category: params.category,
        search: params.search,
        sort_by: params.sortBy,
        limit: params.limit,
        offset: params.offset,
      },
    });
  }

  // -- Plugin ------------------------------------------------------------

  registerPlugin(body: PluginRegisterRequest) {
    return this.request<Plugin>("POST", "/api/v1/plugin/register", { body });
  }
  getPlugin(pluginId: string) {
    return this.request<Plugin>("GET", `/api/v1/plugin/${encodeURIComponent(pluginId)}`);
  }
  installPlugin(body: PluginInstallRequest) {
    return this.request<Plugin>("POST", "/api/v1/plugin/install", { body });
  }
  listInstalledPlugins(tenantId: string) {
    return this.request<Plugin[]>("GET", `/api/v1/plugin/${encodeURIComponent(tenantId)}/installed`);
  }

  // -- Billing -----------------------------------------------------------

  getBillingReport(tenantId?: string) {
    return this.request<BillingReport>("GET", "/api/v1/billing/report", {
      headers: this.tenantHeader(tenantId),
    });
  }
  getBillingBalance(tenantId?: string) {
    return this.request<BillingBalance>("GET", "/api/v1/billing/balance", {
      headers: this.tenantHeader(tenantId),
    });
  }
  getBillingUsage(tenantId?: string, limit = 100) {
    return this.request<UsageRecord[]>("GET", "/api/v1/billing/usage", {
      query: { limit },
      headers: this.tenantHeader(tenantId),
    });
  }
  createSubscription(tier: string, period = "monthly", tenantId?: string) {
    return this.request<unknown>("POST", "/api/v1/billing/subscription", {
      query: { tier, period },
      headers: this.tenantHeader(tenantId),
    });
  }

  // -- Workflow ----------------------------------------------------------

  listWorkflows(tenantId?: string) {
    return this.request<Workflow[]>("GET", "/api/v1/workflow", {
      headers: this.tenantHeader(tenantId),
    });
  }
  createWorkflow(name: string, description = "", tenantId?: string) {
    return this.request<Workflow>("POST", "/api/v1/workflow/create", {
      query: { name, description },
      headers: this.tenantHeader(tenantId),
    });
  }
  runWorkflow(body: WorkflowRunRequest) {
    return this.request<WorkflowExecution>("POST", "/api/v1/workflow/run", { body });
  }
  pauseWorkflow(executionId: string) {
    return this.request<WorkflowExecution>("POST", `/api/v1/workflow/${encodeURIComponent(executionId)}/pause`);
  }
  resumeWorkflow(executionId: string) {
    return this.request<WorkflowExecution>("POST", `/api/v1/workflow/${encodeURIComponent(executionId)}/resume`);
  }
  cancelWorkflow(executionId: string) {
    return this.request<WorkflowExecution>("POST", `/api/v1/workflow/${encodeURIComponent(executionId)}/cancel`);
  }
  getWorkflow(workflowId: string) {
    return this.request<Workflow>("GET", `/api/v1/workflow/${encodeURIComponent(workflowId)}`);
  }
  listWorkflowExecutions(workflowId: string) {
    return this.request<WorkflowExecution[]>(
      "GET",
      `/api/v1/workflow/${encodeURIComponent(workflowId)}/executions`,
    );
  }

  /**
   * Stream workflow execution as Server-Sent Events.
   * Yields raw SSE event payloads (already JSON-parsed when possible).
   */
  async *runWorkflowStream(body: WorkflowRunRequest, signal?: AbortSignal): AsyncIterable<unknown> {
    const url = `${this.baseUrl}/api/v1/workflow/run/stream`;
    const resp = await fetch(url, {
      method: "POST",
      headers: this.baseHeaders({ Accept: "text/event-stream" }),
      body: JSON.stringify(body),
      signal,
    });
    if (!resp.ok || !resp.body) {
      throw new ApiError(resp.status, resp.statusText, await resp.text().catch(() => undefined));
    }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx: number;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const raw = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          const dataLine = raw.split("\n").find((l) => l.startsWith("data:"));
          if (!dataLine) continue;
          const data = dataLine.slice(5).trim();
          if (!data || data === "[DONE]") continue;
          try {
            yield JSON.parse(data);
          } catch {
            yield data;
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  // -- Usage -------------------------------------------------------------

  getUsageSummary(tenantId?: string) {
    return this.request<UsageSummary>("GET", "/api/v1/usage/summary", {
      headers: this.tenantHeader(tenantId),
    });
  }
  getUsageAnalytics(tenantId?: string) {
    return this.request<unknown>("GET", "/api/v1/usage/analytics", {
      headers: this.tenantHeader(tenantId),
    });
  }

  // -- Observability -----------------------------------------------------

  listTraces(params: { limit?: number; tenantId?: string } = {}) {
    return this.request<Trace[]>("GET", "/api/v1/observability/traces", {
      query: { limit: params.limit },
      headers: this.optionalTenantHeader(params.tenantId),
    });
  }
  getTrace(traceId: string) {
    return this.request<Trace>("GET", `/api/v1/observability/traces/${encodeURIComponent(traceId)}`);
  }
  getTraceGraph(traceId: string) {
    return this.request<unknown>("GET", `/api/v1/observability/traces/${encodeURIComponent(traceId)}/graph`);
  }
  getLatencyMetrics(tenantId?: string) {
    return this.request<LatencyMetrics>("GET", "/api/v1/observability/latency", {
      headers: this.optionalTenantHeader(tenantId),
    });
  }
  getTokenUsageStats(tenantId?: string) {
    return this.request<TokenUsageStats>("GET", "/api/v1/observability/tokens", {
      headers: this.optionalTenantHeader(tenantId),
    });
  }
  getActiveTraces() {
    return this.request<Trace[]>("GET", "/api/v1/observability/active-traces");
  }

  // -- header helpers ----------------------------------------------------

  /** Required X-Tenant-ID: uses explicit arg, else falls back to auth store. */
  private tenantHeader(tenantId?: string): Headers {
    const tid = tenantId ?? this.auth.getTenantId() ?? "";
    return { "X-Tenant-ID": tid };
  }

  /** Optional X-Tenant-ID: omitted entirely when no value is available. */
  private optionalTenantHeader(tenantId?: string): Headers {
    const tid = tenantId ?? this.auth.getTenantId();
    return tid ? { "X-Tenant-ID": tid } : {};
  }
}

/** Default singleton client (same-origin base, localStorage auth). */
export const api = new AgentOSClient();

export default api;
