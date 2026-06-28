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
