/**
 * Agent OS V6.0 - JavaScript SDK
 * Official JS/TS SDK for Agent OS Platform
 */
class AgentOSClient {
  /**
   * @param {Object} options
   * @param {string} options.baseUrl - API base URL
   * @param {string} options.apiKey - API key
   * @param {string} options.tenantId - Tenant ID
   */
  constructor({ baseUrl = "http://localhost:8000", apiKey = "", tenantId = "" } = {}) {
    this.baseUrl = baseUrl;
    this.apiKey = apiKey;
    this.tenantId = tenantId;
    this.accessToken = "";
  }

  _headers() {
    const headers = {
      "Content-Type": "application/json",
      "X-Tenant-ID": this.tenantId,
    };
    if (this.accessToken) {
      headers["Authorization"] = `Bearer ${this.accessToken}`;
    }
    if (this.apiKey) {
      headers["X-API-Key"] = this.apiKey;
    }
    return headers;
  }

  async _request(method, path, body = null) {
    const url = `${this.baseUrl}${path}`;
    const options = {
      method,
      headers: this._headers(),
    };
    if (body) {
      options.body = JSON.stringify(body);
    }
    const response = await fetch(url, options);
    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: response.statusText }));
      throw new Error(error.message || `HTTP ${response.status}`);
    }
    return response.json();
  }

  // Auth
  async login(tenantId, email, password) {
    const result = await this._request("POST", "/api/v1/auth/login", {
      tenant_id: tenantId, email, password,
    });
    this.accessToken = result.access_token || "";
    this.tenantId = tenantId;
    return result;
  }

  async register(tenantId, username, email, password) {
    return this._request("POST", "/api/v1/auth/register", {
      tenant_id: tenantId, username, email, password,
    });
  }

  // Tenant
  async createTenant(name, slug, tier = "free") {
    return this._request("POST", "/api/v1/tenant/create", { name, slug, tier });
  }

  async getTenant(tenantId) {
    return this._request("GET", `/api/v1/tenant/${tenantId}`);
  }

  // Agent
  async registerAgent({ name, description = "", agentType = "chat", systemPrompt = "", priceModel = "free", price = 0, tags = [], category = "" } = {}) {
    return this._request("POST", "/api/v1/agent/register", {
      tenant_id: this.tenantId,
      owner_id: "",
      name,
      description,
      agent_type: agentType,
      system_prompt: systemPrompt,
      price_model: priceModel,
      price,
      tags,
      category,
    });
  }

  async getAgent(agentId) {
    return this._request("GET", `/api/v1/agent/${agentId}`);
  }

  async listAgents(limit = 50, offset = 0) {
    return this._request("GET", `/api/v1/agent?limit=${limit}&offset=${offset}`);
  }

  async executeAgent(agentId, userInput, userId = "") {
    return this._request("POST", "/api/v1/agent/execute", {
      agent_id: agentId,
      user_input: userInput,
      user_id: userId,
      tenant_id: this.tenantId,
    });
  }

  async publishAgent(agentId) {
    return this._request("POST", `/api/v1/agent/${agentId}/publish`);
  }

  // Marketplace
  async listMarketplace({ category = "", search = "", sortBy = "newest", limit = 50, offset = 0 } = {}) {
    const params = new URLSearchParams({ category, search, sort_by: sortBy, limit, offset });
    return this._request("GET", `/api/v1/marketplace/list?${params}`);
  }

  async getFeatured() {
    return this._request("GET", "/api/v1/marketplace/featured");
  }

  async searchAgents(query) {
    return this._request("GET", `/api/v1/marketplace/list?search=${encodeURIComponent(query)}`);
  }

  // Billing
  async getBillingReport() {
    return this._request("GET", "/api/v1/billing/report");
  }

  async getBalance() {
    return this._request("GET", "/api/v1/billing/balance");
  }

  // Plugin
  async registerPlugin({ name, description = "", pluginType = "tool", price = 0, priceModel = "free", code = "" } = {}) {
    return this._request("POST", "/api/v1/plugin/register", {
      tenant_id: this.tenantId,
      developer_id: "",
      name,
      description,
      plugin_type: pluginType,
      price,
      price_model: priceModel,
      code,
    });
  }

  async installPlugin(pluginId) {
    return this._request("POST", "/api/v1/plugin/install", {
      tenant_id: this.tenantId,
      plugin_id: pluginId,
    });
  }

  // Workflow
  async createWorkflow(name, description = "") {
    return this._request("POST", `/api/v1/workflow/create?name=${encodeURIComponent(name)}&description=${encodeURIComponent(description)}`);
  }

  async runWorkflow(workflowId, inputData = {}) {
    return this._request("POST", "/api/v1/workflow/run", {
      workflow_id: workflowId,
      input_data: inputData,
    });
  }

  // Usage
  async getUsageSummary() {
    return this._request("GET", "/api/v1/usage/summary");
  }

  async getAnalytics() {
    return this._request("GET", "/api/v1/usage/analytics");
  }

  // Health
  async health() {
    return this._request("GET", "/health");
  }
}

// Node.js export
if (typeof module !== "undefined" && module.exports) {
  module.exports = { AgentOSClient };
}

// Browser global
if (typeof window !== "undefined") {
  window.AgentOSClient = AgentOSClient;
}