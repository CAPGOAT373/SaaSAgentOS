"""
Agent OS V6.0 - Python SDK
Official Python SDK for Agent OS Platform
"""
import requests
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


@dataclass
class AgentOSClient:
    """Agent OS Python SDK Client"""

    base_url: str = "http://localhost:8000"
    api_key: str = ""
    tenant_id: str = ""
    access_token: str = ""

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "X-Tenant-ID": self.tenant_id,
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        kwargs.setdefault("headers", self._headers())
        response = requests.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    # Auth
    def login(self, tenant_id: str, email: str, password: str) -> Dict[str, Any]:
        result = self._request("POST", "/api/v1/auth/login", json={
            "tenant_id": tenant_id, "email": email, "password": password,
        })
        self.access_token = result.get("access_token", "")
        self.tenant_id = tenant_id
        return result

    def register(self, tenant_id: str, username: str, email: str, password: str) -> Dict[str, Any]:
        return self._request("POST", "/api/v1/auth/register", json={
            "tenant_id": tenant_id, "username": username, "email": email, "password": password,
        })

    # Tenant
    def create_tenant(self, name: str, slug: str, tier: str = "free") -> Dict[str, Any]:
        return self._request("POST", "/api/v1/tenant/create", json={
            "name": name, "slug": slug, "tier": tier,
        })

    def get_tenant(self, tenant_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/api/v1/tenant/{tenant_id}")

    # Agent
    def register_agent(
        self, name: str, description: str = "", agent_type: str = "chat",
        system_prompt: str = "", price_model: str = "free", price: float = 0.0,
        tags: Optional[List[str]] = None, category: str = "",
    ) -> Dict[str, Any]:
        return self._request("POST", "/api/v1/agent/register", json={
            "tenant_id": self.tenant_id, "owner_id": "",
            "name": name, "description": description,
            "agent_type": agent_type, "system_prompt": system_prompt,
            "price_model": price_model, "price": price,
            "tags": tags or [], "category": category,
        })

    def get_agent(self, agent_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/api/v1/agent/{agent_id}")

    def list_agents(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        return self._request("GET", f"/api/v1/agent?limit={limit}&offset={offset}")

    def execute_agent(self, agent_id: str, user_input: str, user_id: str = "") -> Dict[str, Any]:
        return self._request("POST", "/api/v1/agent/execute", json={
            "agent_id": agent_id, "user_input": user_input,
            "user_id": user_id, "tenant_id": self.tenant_id,
        })

    def publish_agent(self, agent_id: str) -> Dict[str, Any]:
        return self._request("POST", f"/api/v1/agent/{agent_id}/publish")

    # Marketplace
    def list_marketplace(
        self, category: str = "", search: str = "", sort_by: str = "newest",
        limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        params = f"category={category}&search={search}&sort_by={sort_by}&limit={limit}&offset={offset}"
        return self._request("GET", f"/api/v1/marketplace/list?{params}")

    def get_featured(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/api/v1/marketplace/featured")

    def search_agents(self, query: str) -> List[Dict[str, Any]]:
        return self._request("GET", f"/api/v1/marketplace/list?search={query}")

    # Billing
    def get_billing_report(self) -> Dict[str, Any]:
        return self._request("GET", "/api/v1/billing/report")

    def get_balance(self) -> Dict[str, Any]:
        return self._request("GET", "/api/v1/billing/balance")

    # Plugin
    def register_plugin(
        self, name: str, description: str = "", plugin_type: str = "tool",
        price: float = 0.0, price_model: str = "free", code: str = "",
    ) -> Dict[str, Any]:
        return self._request("POST", "/api/v1/plugin/register", json={
            "tenant_id": self.tenant_id, "developer_id": "",
            "name": name, "description": description,
            "plugin_type": plugin_type, "price": price,
            "price_model": price_model, "code": code,
        })

    def install_plugin(self, plugin_id: str) -> Dict[str, Any]:
        return self._request("POST", "/api/v1/plugin/install", json={
            "tenant_id": self.tenant_id, "plugin_id": plugin_id,
        })

    # Workflow
    def create_workflow(self, name: str, description: str = "") -> Dict[str, Any]:
        return self._request("POST", f"/api/v1/workflow/create?name={name}&description={description}")

    def run_workflow(self, workflow_id: str, input_data: Optional[Dict] = None) -> Dict[str, Any]:
        return self._request("POST", "/api/v1/workflow/run", json={
            "workflow_id": workflow_id, "input_data": input_data or {},
        })

    # Usage
    def get_usage_summary(self) -> Dict[str, Any]:
        return self._request("GET", "/api/v1/usage/summary")

    def get_analytics(self) -> Dict[str, Any]:
        return self._request("GET", "/api/v1/usage/analytics")

    # Health
    def health(self) -> Dict[str, Any]:
        return self._request("GET", "/health")


# Convenience function
def create_client(
    base_url: str = "http://localhost:8000",
    api_key: str = "", tenant_id: str = "",
) -> AgentOSClient:
    return AgentOSClient(base_url=base_url, api_key=api_key, tenant_id=tenant_id)