/**
 * Agent OS V6.0 - API schema types (auto-generated from OpenAPI.JSON)
 *
 * Regenerate with:  npm run generate:api
 *   (openapi-typescript ../OpenAPI.JSON -o src/api/schema.ts)
 *
 * This file mirrors the openapi-typescript output shape (a `paths` map plus a
 * `components.schemas` namespace) so it is a drop-in replacement for the
 * generated artifact. It is kept spec-accurate: request bodies are fully typed
 * from the OpenAPI component schemas; response bodies that the backend left
 * without a schema (empty `{}`) are typed as `unknown`.
 *
 * Hand-curated, backend-derived response models live in `./types.ts` and are
 * surfaced through the typed client in `./client.ts`.
 */

// ---------------------------------------------------------------------------
// Component schemas (request bodies + error models) - verbatim from OpenAPI
// ---------------------------------------------------------------------------

export interface LoginRequest {
  /** Tenant ID */
  tenant_id: string;
  /** User email */
  email: string;
  /** User password */
  password: string;
}

export interface IdentityCreateRequest {
  tenant_id: string;
  username: string;
  email: string;
  password: string;
}

export interface TenantCreateRequest {
  /** @minLength 2 @maxLength 100 */
  name: string;
  /** @minLength 2 @maxLength 50 @pattern ^[a-z0-9-]+$ */
  slug: string;
  tier?: string;
  region?: string | null;
}

export interface AgentRegisterRequest {
  tenant_id: string;
  owner_id: string;
  /** @minLength 1 @maxLength 200 */
  name: string;
  description?: string;
  agent_type?: string;
  system_prompt?: string;
  price_model?: string;
  price?: number;
  tags?: unknown[] | null;
  category?: string;
}

export interface AgentExecuteRequest {
  agent_id: string;
  user_input: string;
  user_id?: string;
  tenant_id?: string;
}

export interface PluginRegisterRequest {
  tenant_id: string;
  developer_id: string;
  name: string;
  description?: string;
  plugin_type?: string;
  price?: number;
  price_model?: string;
  code?: string;
}

export interface PluginInstallRequest {
  tenant_id: string;
  plugin_id: string;
}

export interface WorkflowRunRequest {
  workflow_id: string;
  input_data?: Record<string, unknown> | null;
}

export interface ValidationError {
  loc: Array<string | number>;
  msg: string;
  type: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}

export interface HTTPValidationError {
  detail?: ValidationError[];
}

// ---------------------------------------------------------------------------
// paths - openapi-typescript compatible operation map
// ---------------------------------------------------------------------------

/** Media-type keyed response body. Spec-unknown responses resolve to `unknown`. */
type JsonBody<T> = { content: { "application/json": T } };
type OkResponse<T = unknown> = { 200: JsonBody<T>; 422?: JsonBody<HTTPValidationError> };
type OkOnly = { 200: JsonBody<unknown> };

export interface paths {
  "/health": {
    get: { responses: OkOnly };
  };
  "/metrics": {
    get: { responses: { 200: { content: { "text/plain": string } } } };
  };

  "/api/v1/observability/traces": {
    get: {
      parameters: {
        query?: { limit?: number };
        header?: { "X-Tenant-ID"?: string };
      };
      responses: OkResponse;
    };
  };
  "/api/v1/observability/traces/{trace_id}": {
    get: {
      parameters: { path: { trace_id: string } };
      responses: OkResponse;
    };
  };
  "/api/v1/observability/traces/{trace_id}/graph": {
    get: {
      parameters: { path: { trace_id: string } };
      responses: OkResponse;
    };
  };
  "/api/v1/observability/latency": {
    get: {
      parameters: { header?: { "X-Tenant-ID"?: string } };
      responses: OkResponse;
    };
  };
  "/api/v1/observability/tokens": {
    get: {
      parameters: { header?: { "X-Tenant-ID"?: string } };
      responses: OkResponse;
    };
  };
  "/api/v1/observability/active-traces": {
    get: { responses: OkOnly };
  };

  "/api/v1/auth/login": {
    post: {
      requestBody: { content: { "application/json": LoginRequest } };
      responses: OkResponse;
    };
  };
  "/api/v1/auth/register": {
    post: {
      requestBody: { content: { "application/json": IdentityCreateRequest } };
      responses: OkResponse;
    };
  };
  "/api/v1/auth/me": {
    get: {
      responses: OkOnly;
    };
  };

  "/api/v1/tenant/create": {
    post: {
      requestBody: { content: { "application/json": TenantCreateRequest } };
      responses: OkResponse;
    };
  };
  "/api/v1/tenant/{tenant_id}": {
    get: {
      parameters: { path: { tenant_id: string } };
      responses: OkResponse;
    };
  };
  "/api/v1/tenant": {
    get: {
      parameters: { query?: { region?: string | null } };
      responses: OkResponse;
    };
  };

  "/api/v1/agent/register": {
    post: {
      requestBody: { content: { "application/json": AgentRegisterRequest } };
      responses: OkResponse;
    };
  };
  "/api/v1/agent/{agent_id}": {
    get: {
      parameters: { path: { agent_id: string } };
      responses: OkResponse;
    };
  };
  "/api/v1/agent": {
    get: {
      parameters: {
        query?: { tenant_id?: string | null; limit?: number; offset?: number };
      };
      responses: OkResponse;
    };
  };
  "/api/v1/agent/execute": {
    post: {
      requestBody: { content: { "application/json": AgentExecuteRequest } };
      responses: OkResponse;
    };
  };
  "/api/v1/agent/execute/stream": {
    post: {
      requestBody: { content: { "application/json": AgentExecuteRequest } };
      responses: OkResponse;
    };
  };
  "/api/v1/agent/{agent_id}/executions": {
    get: {
      parameters: {
        path: { agent_id: string };
        query?: { limit?: number };
      };
      responses: OkResponse;
    };
  };
  "/api/v1/agent/{agent_id}/publish": {
    post: {
      parameters: { path: { agent_id: string } };
      responses: OkResponse;
    };
  };
  "/api/v1/agent/{agent_id}/purchase": {
    post: {
      parameters: {
        path: { agent_id: string };
        header: { "X-Tenant-ID": string; "X-User-ID": string };
      };
      responses: OkResponse;
    };
  };
  "/api/v1/agent/{agent_id}/review": {
    post: {
      parameters: {
        path: { agent_id: string };
        query: { rating: number; comment?: string };
      };
      responses: OkResponse;
    };
  };

  "/api/v1/marketplace/list": {
    get: {
      parameters: {
        query?: { category?: string; search?: string; sort_by?: string; limit?: number; offset?: number };
      };
      responses: OkResponse;
    };
  };
  "/api/v1/marketplace/featured": {
    get: { responses: OkOnly };
  };
  "/api/v1/marketplace/categories": {
    get: { responses: OkOnly };
  };
  "/api/v1/marketplace/plugins": {
    get: {
      parameters: {
        query?: { category?: string; search?: string; sort_by?: string; limit?: number; offset?: number };
      };
      responses: OkResponse;
    };
  };

  "/api/v1/plugin/register": {
    post: {
      requestBody: { content: { "application/json": PluginRegisterRequest } };
      responses: OkResponse;
    };
  };
  "/api/v1/plugin/{plugin_id}": {
    get: {
      parameters: { path: { plugin_id: string } };
      responses: OkResponse;
    };
  };
  "/api/v1/plugin/install": {
    post: {
      requestBody: { content: { "application/json": PluginInstallRequest } };
      responses: OkResponse;
    };
  };
  "/api/v1/plugin/{tenant_id}/installed": {
    get: {
      parameters: { path: { tenant_id: string } };
      responses: OkResponse;
    };
  };

  "/api/v1/billing/report": {
    get: {
      parameters: { header: { "X-Tenant-ID": string } };
      responses: OkResponse;
    };
  };
  "/api/v1/billing/balance": {
    get: {
      parameters: { header: { "X-Tenant-ID": string } };
      responses: OkResponse;
    };
  };
  "/api/v1/billing/usage": {
    get: {
      parameters: {
        query?: { limit?: number };
        header: { "X-Tenant-ID": string };
      };
      responses: OkResponse;
    };
  };
  "/api/v1/billing/subscription": {
    post: {
      parameters: {
        query: { tier: string; period?: string };
        header: { "X-Tenant-ID": string };
      };
      responses: OkResponse;
    };
  };

  "/api/v1/workflow": {
    get: {
      parameters: { header?: { "X-Tenant-ID"?: string } };
      responses: OkResponse;
    };
  };
  "/api/v1/workflow/create": {
    post: {
      parameters: {
        query: { name: string; description?: string };
        header: { "X-Tenant-ID": string };
      };
      responses: OkResponse;
    };
  };
  "/api/v1/workflow/run": {
    post: {
      requestBody: { content: { "application/json": WorkflowRunRequest } };
      responses: OkResponse;
    };
  };
  "/api/v1/workflow/run/stream": {
    post: {
      requestBody: { content: { "application/json": WorkflowRunRequest } };
      responses: OkResponse;
    };
  };
  "/api/v1/workflow/{execution_id}/pause": {
    post: {
      parameters: { path: { execution_id: string } };
      responses: OkResponse;
    };
  };
  "/api/v1/workflow/{execution_id}/resume": {
    post: {
      parameters: { path: { execution_id: string } };
      responses: OkResponse;
    };
  };
  "/api/v1/workflow/{execution_id}/cancel": {
    post: {
      parameters: { path: { execution_id: string } };
      responses: OkResponse;
    };
  };
  "/api/v1/workflow/{workflow_id}": {
    get: {
      parameters: { path: { workflow_id: string } };
      responses: OkResponse;
    };
  };
  "/api/v1/workflow/{workflow_id}/executions": {
    get: {
      parameters: { path: { workflow_id: string } };
      responses: OkResponse;
    };
  };

  "/api/v1/usage/summary": {
    get: {
      parameters: { header: { "X-Tenant-ID": string } };
      responses: OkResponse;
    };
  };
  "/api/v1/usage/analytics": {
    get: {
      parameters: { header: { "X-Tenant-ID": string } };
      responses: OkResponse;
    };
  };

  "/api/v1/admin/health/all": {
    get: { responses: OkOnly };
  };
}

// ---------------------------------------------------------------------------
// components namespace (openapi-typescript compatible)
// ---------------------------------------------------------------------------

export interface components {
  schemas: {
    LoginRequest: LoginRequest;
    IdentityCreateRequest: IdentityCreateRequest;
    TenantCreateRequest: TenantCreateRequest;
    AgentRegisterRequest: AgentRegisterRequest;
    AgentExecuteRequest: AgentExecuteRequest;
    PluginRegisterRequest: PluginRegisterRequest;
    PluginInstallRequest: PluginInstallRequest;
    WorkflowRunRequest: WorkflowRunRequest;
    ValidationError: ValidationError;
    HTTPValidationError: HTTPValidationError;
  };
}

export interface operations {
  health_check: paths["/health"]["get"];
  metrics: paths["/metrics"]["get"];
  traces_list: paths["/api/v1/observability/traces"]["get"];
  trace_get: paths["/api/v1/observability/traces/{trace_id}"]["get"];
  trace_graph: paths["/api/v1/observability/traces/{trace_id}/graph"]["get"];
  latency_metrics: paths["/api/v1/observability/latency"]["get"];
  token_usage_stats: paths["/api/v1/observability/tokens"]["get"];
  active_traces: paths["/api/v1/observability/active-traces"]["get"];
  auth_login: paths["/api/v1/auth/login"]["post"];
  auth_register: paths["/api/v1/auth/register"]["post"];
  auth_me: paths["/api/v1/auth/me"]["get"];
  tenant_create: paths["/api/v1/tenant/create"]["post"];
  tenant_get: paths["/api/v1/tenant/{tenant_id}"]["get"];
  tenant_list: paths["/api/v1/tenant"]["get"];
  agent_register: paths["/api/v1/agent/register"]["post"];
  agent_get: paths["/api/v1/agent/{agent_id}"]["get"];
  agent_list: paths["/api/v1/agent"]["get"];
  agent_execute: paths["/api/v1/agent/execute"]["post"];
  agent_execute_stream: paths["/api/v1/agent/execute/stream"]["post"];
  agent_executions: paths["/api/v1/agent/{agent_id}/executions"]["get"];
  agent_publish: paths["/api/v1/agent/{agent_id}/publish"]["post"];
  agent_purchase: paths["/api/v1/agent/{agent_id}/purchase"]["post"];
  agent_review: paths["/api/v1/agent/{agent_id}/review"]["post"];
  marketplace_list: paths["/api/v1/marketplace/list"]["get"];
  marketplace_featured: paths["/api/v1/marketplace/featured"]["get"];
  marketplace_categories: paths["/api/v1/marketplace/categories"]["get"];
  marketplace_plugins: paths["/api/v1/marketplace/plugins"]["get"];
  plugin_register: paths["/api/v1/plugin/register"]["post"];
  plugin_get: paths["/api/v1/plugin/{plugin_id}"]["get"];
  plugin_install: paths["/api/v1/plugin/install"]["post"];
  plugin_installed: paths["/api/v1/plugin/{tenant_id}/installed"]["get"];
  billing_report: paths["/api/v1/billing/report"]["get"];
  billing_balance: paths["/api/v1/billing/balance"]["get"];
  billing_usage: paths["/api/v1/billing/usage"]["get"];
  billing_subscription: paths["/api/v1/billing/subscription"]["post"];
  workflow_list: paths["/api/v1/workflow"]["get"];
  workflow_create: paths["/api/v1/workflow/create"]["post"];
  workflow_run: paths["/api/v1/workflow/run"]["post"];
  workflow_run_stream: paths["/api/v1/workflow/run/stream"]["post"];
  workflow_pause: paths["/api/v1/workflow/{execution_id}/pause"]["post"];
  workflow_resume: paths["/api/v1/workflow/{execution_id}/resume"]["post"];
  workflow_cancel: paths["/api/v1/workflow/{execution_id}/cancel"]["post"];
  workflow_get: paths["/api/v1/workflow/{workflow_id}"]["get"];
  workflow_executions: paths["/api/v1/workflow/{workflow_id}/executions"]["get"];
  usage_summary: paths["/api/v1/usage/summary"]["get"];
  usage_analytics: paths["/api/v1/usage/analytics"]["get"];
  admin_health_all: paths["/api/v1/admin/health/all"]["get"];
}
