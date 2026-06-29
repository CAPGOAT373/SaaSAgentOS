/**
 * Agent OS V6.0 - Mock Data
 *
 * Centralized mock data for all domains. Pages import from here
 * instead of calling the backend HTTP API. Switch to real API by
 * toggling the import source (services/api vs services/mock).
 */

// ---------------------------------------------------------------------------
// Workflows
// ---------------------------------------------------------------------------

export const mockWorkflows = [
  {
    workflow_id: "wf-001",
    tenant_id: "agentos",
    name: "Customer Support Pipeline",
    description: "Multi-agent pipeline for automated customer support triage, routing, and resolution.",
    status: "draft",
    created_at: "2026-06-27T14:22:00Z",
    updated_at: "2026-06-28T09:00:00Z",
    nodes: [],
    edges: [],
  },
  {
    workflow_id: "wf-002",
    tenant_id: "agentos",
    name: "Code Review Workflow",
    description: "Automated code review with linting, security scanning, and PR summarization.",
    status: "draft",
    created_at: "2026-06-26T10:00:00Z",
    updated_at: "2026-06-27T16:30:00Z",
    nodes: [],
    edges: [],
  },
  {
    workflow_id: "wf-003",
    tenant_id: "agentos",
    name: "Data ETL Pipeline",
    description: "Extract, transform, and load pipeline with validation and error handling stages.",
    status: "draft",
    created_at: "2026-06-25T08:00:00Z",
    updated_at: "2026-06-26T12:00:00Z",
    nodes: [],
    edges: [],
  },
];

// ---------------------------------------------------------------------------
// Agents
// ---------------------------------------------------------------------------

export const mockAgents = [
  {
    agent_id: "ag-001",
    tenant_id: "agentos",
    owner_id: "user-admin",
    name: "Customer Support Agent",
    description: "AI agent for handling customer inquiries with sentiment analysis and auto-escalation.",
    agent_type: "chat",
    system_prompt: "You are a helpful customer support agent. Always be polite and professional.",
    price_model: "free",
    price: 0,
    status: "draft",
    created_at: "2026-06-27T10:00:00Z",
  },
  {
    agent_id: "ag-002",
    tenant_id: "agentos",
    owner_id: "user-admin",
    name: "Code Review Assistant",
    description: "Automated code review agent that checks PRs for style, bugs, and security issues.",
    agent_type: "chat",
    system_prompt: "You are a senior code reviewer. Provide concise, actionable feedback.",
    price_model: "free",
    price: 0,
    status: "published",
    created_at: "2026-06-26T09:00:00Z",
  },
  {
    agent_id: "ag-003",
    tenant_id: "agentos",
    owner_id: "user-admin",
    name: "Data Analyzer",
    description: "Data analysis agent with natural language querying and visualization generation.",
    agent_type: "chat",
    system_prompt: "You are a data analysis expert. Help users understand their data.",
    price_model: "paid",
    price: 9.99,
    status: "draft",
    created_at: "2026-06-25T15:00:00Z",
  },
];

// ---------------------------------------------------------------------------
// Files
// ---------------------------------------------------------------------------

export const mockFiles = [
  { id: "f-001", filename: "knowledge-base-2024.pdf", size: 2457600, uploaded_at: "2026-06-28T10:00:00Z" },
  { id: "f-002", filename: "company-policy-v3.docx", size: 512000, uploaded_at: "2026-06-27T14:00:00Z" },
  { id: "f-003", filename: "README.md", size: 4096, uploaded_at: "2026-06-26T09:00:00Z" },
];

// ---------------------------------------------------------------------------
// Models
// ---------------------------------------------------------------------------

export const mockModels = [
  { id: "openai-gpt4", name: "GPT-4o", provider: "OpenAI", base_url: "https://api.openai.com/v1", api_key_status: "configured", created_at: "2026-01-15T00:00:00Z" },
  { id: "anthropic-claude", name: "Claude 3.5 Sonnet", provider: "Anthropic", base_url: "https://api.anthropic.com", api_key_status: "configured", created_at: "2026-02-01T00:00:00Z" },
  { id: "local-llama", name: "Llama 3.3 70B", provider: "Local", base_url: "http://localhost:11434", api_key_status: "missing", created_at: "2026-03-10T00:00:00Z" },
];

// ---------------------------------------------------------------------------
// Tasks
// ---------------------------------------------------------------------------

export const mockTasks = [
  { id: "t-001", name: "Customer Support — ETL Pipeline", status: "completed", created_at: "2026-06-27T14:22:00Z", duration: 3420 },
  { id: "t-002", name: "Code Review — PR #1287", status: "running", created_at: "2026-06-28T08:15:00Z", duration: 0 },
  { id: "t-003", name: "Data Analysis — Q2 Report", status: "failed", created_at: "2026-06-28T09:30:00Z", duration: 12500 },
  { id: "t-004", name: "Agent Execution — ChatBot v2", status: "pending", created_at: "2026-06-28T10:00:00Z", duration: 0 },
  { id: "t-005", name: "Knowledge Base — Index Rebuild", status: "completed", created_at: "2026-06-25T16:00:00Z", duration: 8900 },
];

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export const mockSettings = {
  system_name: "Agent OS",
  default_model: "GPT-4o",
  timezone: "UTC",
  log_level: "INFO",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Simulate async fetch delay (200-600ms) */
export function delay(ms?: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms ?? 200 + Math.random() * 400));
}

// ---------------------------------------------------------------------------
// Dashboard / Health
// ---------------------------------------------------------------------------

export const mockHealth = {
  status: "healthy" as const,
  service: "Agent OS API Gateway",
  version: "6.0.0",
  timestamp: Date.now() / 1000,
};

export const mockAdminHealth = {
  status: "healthy",
  services: {
    tenant_manager:  { status: "healthy", service: "TenantManager",  total_tenants: 1,    regions: 1 },
    iam:             { status: "healthy", service: "IAMService",     total_identities: 1, audit_log_entries: 11 },
    billing:         { status: "healthy", service: "BillingEngine",  subscriptions: 0,    invoices: 0, credits_accounts: 0 },
    agent_economy:   { status: "healthy", service: "AgentEconomy",   total_agents: 3,     total_purchases: 0 },
    plugin_runtime:  { status: "healthy", service: "PluginRuntime",  total_plugins: 0,    total_installs: 0 },
    llm_gateway:     { status: "healthy", service: "LLMGateway",     providers: "openai anthropic local", allow_mock: false },
    agent_runtime:   { status: "healthy", service: "AgentRuntimeV3", total_agents: 0,     total_executions: 0, total_tools: 0 },
    memory:          { status: "healthy", service: "MemorySystem",   total_entries: 0,    agents_with_memory: 0 },
  } as Record<string, { status: string; service: string; [k: string]: unknown }>,
};

// ---------------------------------------------------------------------------
// Tasks detail (execution logs)
// ---------------------------------------------------------------------------

export const mockTaskLogs: Record<string, string[]> = {
  "t-001": ["[14:22:01] Task started","[14:24:30] Stage 1 completed","[14:26:15] Stage 2 completed","[14:27:10] Task finished successfully"],
  "t-002": ["[08:15:00] Task started","[08:15:30] Processing file analysis","[08:16:00] Running security scan..."],
  "t-003": ["[09:30:00] Task started","[09:32:00] Processing data","[09:35:00] Error: Data format mismatch","[09:35:01] Task failed"],
  "t-004": ["[10:00:00] Task queued — waiting for agent runtime"],
  "t-005": ["[16:00:00] Task started","[16:05:00] Indexing documents","[16:12:00] Rebuild complete"],
};

// ---------------------------------------------------------------------------
// Marketplace
// ---------------------------------------------------------------------------

export const mockMarketplaceAgents = [
  { agent_id: "mp-001", name: "Customer Support Pro", description: "Enterprise-grade customer support agent with multi-language support.", category: "Support", price_model: "paid", price: 29.99, rating: 4.8, review_count: 124, creator: "Acme Corp" },
  { agent_id: "mp-002", name: "Code Reviewer AI", description: "Automated PR review with deep code analysis and security scanning.", category: "DevTools", price_model: "freemium", price: 0, rating: 4.5, review_count: 89, creator: "DevAI Labs" },
  { agent_id: "mp-003", name: "Data Analyzer Pro", description: "Natural language data analysis with visualization export.", category: "Analytics", price_model: "paid", price: 49.99, rating: 4.2, review_count: 56, creator: "DataCorp" },
  { agent_id: "mp-004", name: "Legal Doc Assistant", description: "Review and summarize legal documents with compliance checks.", category: "Legal", price_model: "subscription", price: 99, rating: 4.9, review_count: 31, creator: "LegalAI Inc" },
  { agent_id: "mp-005", name: "Open Source HelpBot", description: "Community-maintained general-purpose chatbot.", category: "General", price_model: "free", price: 0, rating: 4.0, review_count: 210, creator: "Community" },
];

// ---------------------------------------------------------------------------
// Billing
// ---------------------------------------------------------------------------

export const mockBillingBalance = {
  tenant_id: "agentos",
  balance: 245.50,
  currency: "USD",
  credits: 1200,
};

export const mockBillingUsage = {
  tenant_id: "agentos",
  total_calls: 1847,
  total_tokens: 256400,
  total_cost: 18.32,
  period: "June 2026",
};

// ---------------------------------------------------------------------------
// Workflow detail (enriched)
// ---------------------------------------------------------------------------

export function getMockWorkflowDetail(id: string) {
  const wf = mockWorkflows.find(w => w.workflow_id === id);
  if (!wf) return null;
  return {
    ...wf,
    nodes: [{ node_id: "n1", name: "Start", node_type: "start" }, { node_id: "n2", name: "Process", node_type: "agent" }, { node_id: "n3", name: "End", node_type: "end" }],
    edges: [{ source: "n1", target: "n2" }, { source: "n2", target: "n3" }],
    executions: [],
  };
}

// ---------------------------------------------------------------------------
// Agent detail (enriched)
// ---------------------------------------------------------------------------

export function getMockAgentDetail(id: string) {
  return mockAgents.find(a => a.agent_id === id) ?? null;
}

// ---------------------------------------------------------------------------
// Task detail (enriched)
// ---------------------------------------------------------------------------

export function getMockTaskDetail(id: string) {
  const t = mockTasks.find(t => t.id === id);
  if (!t) return null;
  return { ...t, logs: mockTaskLogs[id] ?? [] };
}

// ---------------------------------------------------------------------------
// Model test (local)
// ---------------------------------------------------------------------------

export function runMockModelTest(modelId: string): { success: boolean; message: string; latency_ms: number } {
  const model = mockModels.find(m => m.id === modelId);
  if (!model) return { success: false, message: "Model not found", latency_ms: 0 };
  if (model.api_key_status === "missing") return { success: false, message: "API key not configured. Please add an API key in Settings.", latency_ms: 0 };
  if (model.api_key_status === "error") return { success: false, message: "API key invalid or expired. Please check your credentials.", latency_ms: 0 };
  const ok = Math.random() > 0.2;
  const latency = ok ? Math.floor(20 + Math.random() * 380) : 0;
  return { success: ok, message: ok ? `Connection OK (${latency}ms)` : "Connection timed out — the model provider may be unreachable.", latency_ms: latency };
}
