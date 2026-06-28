const API_BASE = '/api/v1';

interface RequestOptions {
  method?: string;
  body?: any;
  headers?: Record<string, string>;
}

class ApiClient {
  private token: string | null = null;

  setToken(token: string | null) {
    this.token = token;
    localStorage.setItem('auth_token', token || '');
  }

  getToken(): string | null {
    if (!this.token) {
      this.token = localStorage.getItem('auth_token');
    }
    return this.token;
  }

  private async request(path: string, options: RequestOptions = {}): Promise<any> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...options.headers,
    };
    const token = this.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const resp = await fetch(`${API_BASE}${path}`, {
      method: options.method || 'GET',
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ error: { message: resp.statusText } }));
      throw new Error(err.error?.message || resp.statusText);
    }

    return resp.json();
  }

  // Auth
  async login(tenantId: string, email: string, password: string) {
    return this.request('/auth/login', {
      method: 'POST',
      body: { tenant_id: tenantId, email, password },
    });
  }

  async register(tenantId: string, username: string, email: string, password: string) {
    return this.request('/auth/register', {
      method: 'POST',
      body: { tenant_id: tenantId, username, email, password },
    });
  }

  async getMe() {
    return this.request('/auth/me');
  }

  // Tenant
  async createTenant(name: string, slug: string, tier: string = 'free') {
    return this.request('/tenant/create', {
      method: 'POST',
      body: { name, slug, tier },
    });
  }

  async getTenant(tenantId: string) {
    return this.request(`/tenant/${tenantId}`);
  }

  // Agent
  async registerAgent(agent: {
    tenant_id: string; owner_id: string; name: string; description: string;
    agent_type?: string; system_prompt?: string; price_model?: string; price?: number;
    tags?: string[]; category?: string;
  }) {
    return this.request('/agent/register', { method: 'POST', body: agent });
  }

  async getAgent(agentId: string) {
    return this.request(`/agent/${agentId}`);
  }

  async listAgents(tenantId?: string, limit: number = 50, offset: number = 0) {
    const params = new URLSearchParams();
    if (tenantId) params.set('tenant_id', tenantId);
    params.set('limit', String(limit));
    params.set('offset', String(offset));
    return this.request(`/agent?${params}`);
  }

  async executeAgent(agentId: string, userInput: string, userId: string = '', tenantId: string = '') {
    return this.request('/agent/execute', {
      method: 'POST',
      body: { agent_id: agentId, user_input: userInput, user_id: userId, tenant_id: tenantId },
    });
  }

  async getAgentExecutions(agentId: string, limit: number = 50) {
    return this.request(`/agent/${agentId}/executions?limit=${limit}`);
  }

  // Workflow
  async createWorkflow(name: string, description: string, tenantId: string) {
    const params = new URLSearchParams({ name, description });
    return this.request(`/workflow/create?${params}`, {
      method: 'POST',
      headers: { 'X-Tenant-ID': tenantId },
    });
  }

  async runWorkflow(workflowId: string, inputData: Record<string, any> = {}) {
    return this.request('/workflow/run', {
      method: 'POST',
      body: { workflow_id: workflowId, input_data: inputData },
    });
  }

  async getWorkflow(workflowId: string) {
    return this.request(`/workflow/${workflowId}`);
  }

  // Billing
  async getBillingBalance(tenantId: string) {
    return this.request('/billing/balance', {
      headers: { 'X-Tenant-ID': tenantId },
    });
  }

  async getUsageSummary(tenantId: string) {
    return this.request('/usage/summary', {
      headers: { 'X-Tenant-ID': tenantId },
    });
  }

  // Marketplace
  async getMarketplaceList(category: string = '', search: string = '', sortBy: string = 'newest') {
    const params = new URLSearchParams({ category, search, sort_by: sortBy });
    return this.request(`/marketplace/list?${params}`);
  }

  // Health
  async getHealth() {
    return this.request('/../health');
  }

  async getAdminHealth() {
    return this.request('/admin/health/all');
  }
}

export const api = new ApiClient();
export default api;