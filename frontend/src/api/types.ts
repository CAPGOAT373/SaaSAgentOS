/**
 * Agent OS V6.0 - curated domain / response types
 *
 * The OpenAPI spec (schema.ts) defines every request body precisely, but the
 * FastAPI handlers return untyped dicts/objects, so response schemas are empty
 * `{}` and resolve to `unknown`. This file fills in the response contracts by
 * reading the backend service layer directly (IAMService.authenticate,
 * Identity.to_dict, health handlers, etc.).
 *
 * Conventions:
 *  - `Verified` types mirror a concrete `to_dict()`/return literal in the
 *    backend and are reliable.
 *  - `Inferred` types are derived from service behaviour where the backend
 *    returns a model whose exact field set was not pinned down; treat the
 *    listed fields as the expected shape but keep them permissive.
 */

// ---------------------------------------------------------------------------
// Auth / Identity  (Verified: IAMService.authenticate + Identity.to_dict)
// ---------------------------------------------------------------------------

export type Role =
  | "super_admin"
  | "tenant_admin"
  | "developer"
  | "user"
  | "viewer"
  | "agent";

/** Verified against Identity.to_dict(safe=True) */
export interface Identity {
  user_id: string;
  tenant_id: string;
  username: string;
  email: string;
  roles: Role[];
  mfa_enabled: boolean;
  sso_provider: string;
  created_at: string;
  last_login: string;
  is_active: boolean;
}

/** Verified against IAMService.authenticate return value */
export interface AuthLoginResponse {
  access_token: string;
  token_type: "bearer";
  user: Identity;
}

/** /api/v1/auth/register returns Identity (safe) */
export type AuthRegisterResponse = Identity;

/** /api/v1/auth/me returns Identity (safe) */
export type AuthMeResponse = Identity;

// ---------------------------------------------------------------------------
// System / Health  (Verified: gateway health handlers)
// ---------------------------------------------------------------------------

/** Verified against the /health handler */
export interface HealthResponse {
  status: "healthy";
  service: string;
  version: string;
  timestamp: number;
}

/** Inferred: /api/v1/admin/health/all maps service name -> health_check() */
export interface AdminHealthAllResponse {
  status: string;
  services: Record<
    | "tenant_manager"
    | "iam"
    | "billing"
    | "agent_economy"
    | "plugin_runtime"
    | "llm_gateway"
    | "agent_runtime"
    | "memory",
    { status: string; service: string; [k: string]: unknown }
  >;
}

// ---------------------------------------------------------------------------
// Tenant  (Inferred: TenantManager models expose id/name/slug/tier/region)
// ---------------------------------------------------------------------------

export type TenantTier = "free" | "pro" | "business" | "enterprise";

export interface Tenant {
  tenant_id: string;
  name: string;
  slug: string;
  tier: TenantTier | string;
  region?: string;
  created_at?: string;
  is_active?: boolean;
  [k: string]: unknown;
}

// ---------------------------------------------------------------------------
// Agent economy  (Inferred: AgentAsset.to_dict + AgentExecution.to_dict)
// ---------------------------------------------------------------------------

export type PriceModel = "free" | "paid" | "freemium" | "subscription";
export type AgentStatus = "draft" | "published" | "archived";

export interface Agent {
  agent_id: string;
  tenant_id: string;
  owner_id: string;
  name: string;
  description: string;
  agent_type?: string;
  system_prompt?: string;
  price_model: PriceModel | string;
  price: number;
  tags?: string[] | null;
  category?: string;
  status?: AgentStatus | string;
  rating?: number;
  review_count?: number;
  execution_count?: number;
  created_at?: string;
  updated_at?: string;
  [k: string]: unknown;
}

export interface AgentExecution {
  execution_id: string;
  agent_id: string;
  tenant_id?: string;
  user_id?: string;
  user_input: string;
  output?: string;
  status?: string;
  tokens_used?: number;
  latency_ms?: number;
  created_at?: string;
  [k: string]: unknown;
}

export interface AgentReview {
  review_id: string;
  agent_id: string;
  tenant_id: string;
  user_id: string;
  rating: number;
  comment: string;
  created_at?: string;
  [k: string]: unknown;
}

// ---------------------------------------------------------------------------
// Marketplace / Plugin  (Inferred)
// ---------------------------------------------------------------------------

export interface MarketplaceAgent extends Agent {
  creator?: string;
  license_type?: string;
}

export interface Plugin {
  plugin_id: string;
  tenant_id: string;
  developer_id: string;
  name: string;
  description: string;
  plugin_type: string;
  price: number;
  price_model: PriceModel | string;
  status?: string;
  created_at?: string;
  [k: string]: unknown;
}

// ---------------------------------------------------------------------------
// Billing / Usage  (Inferred: BillingService return shapes)
// ---------------------------------------------------------------------------

export interface BillingBalance {
  tenant_id: string;
  balance: number;
  currency?: string;
  credits?: number;
  [k: string]: unknown;
}

export interface BillingReport {
  tenant_id: string;
  period?: string;
  total_revenue?: number;
  total_usage?: number;
  platform_fee?: number;
  creator_payout?: number;
  [k: string]: unknown;
}

export interface UsageRecord {
  record_id: string;
  tenant_id: string;
  agent_id?: string;
  user_id?: string;
  tokens_used?: number;
  cost?: number;
  created_at?: string;
  [k: string]: unknown;
}

export interface UsageSummary {
  tenant_id: string;
  total_calls?: number;
  total_tokens?: number;
  total_cost?: number;
  period?: string;
  [k: string]: unknown;
}

// ---------------------------------------------------------------------------
// Workflow  (Inferred: WorkflowEngine models)
// ---------------------------------------------------------------------------

export interface Workflow {
  workflow_id: string;
  tenant_id: string;
  name: string;
  description: string;
  nodes?: unknown[];
  edges?: unknown[];
  status?: string;
  created_at?: string;
  [k: string]: unknown;
}

export type WorkflowExecutionStatus =
  | "pending"
  | "running"
  | "paused"
  | "completed"
  | "failed"
  | "cancelled";

export interface WorkflowExecution {
  execution_id: string;
  workflow_id: string;
  tenant_id?: string;
  status: WorkflowExecutionStatus | string;
  input_data?: Record<string, unknown>;
  output_data?: Record<string, unknown>;
  started_at?: string;
  completed_at?: string;
  [k: string]: unknown;
}

// ---------------------------------------------------------------------------
// Observability  (Inferred: trace manager return shapes)
// ---------------------------------------------------------------------------

export interface Trace {
  trace_id: string;
  name?: string;
  status?: string;
  start_time?: string;
  end_time?: string;
  duration_ms?: number;
  spans?: unknown[];
  [k: string]: unknown;
}

export interface LatencyMetrics {
  p50?: number;
  p95?: number;
  p99?: number;
  avg?: number;
  [k: string]: unknown;
}

export interface TokenUsageStats {
  total_tokens?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  by_model?: Record<string, number>;
  [k: string]: unknown;
}

// ---------------------------------------------------------------------------
// Error envelope  (Verified: FastAPI HTTPException + ValidationError)
// ---------------------------------------------------------------------------

export interface ApiError {
  detail: string | import("./schema").ValidationError[];
}
