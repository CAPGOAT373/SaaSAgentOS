"""
Agent OS V6.0 - Marketplace Service
Unified marketplace API for agents and plugins
"""
from typing import Optional, Dict, Any, List
from agent_os.core_platform.base import BaseService, ServiceContext
from agent_os.marketplace.agent_store import get_agent_store
from agent_os.marketplace.plugin_store import get_plugin_store
from agent_os.marketplace.pricing_engine import get_pricing_engine
from agent_os.marketplace.revenue_share import get_revenue_share


class MarketplaceService(BaseService):
    """Marketplace Service: unified storefront for agents and plugins"""

    def __init__(self):
        super().__init__()
        self._agent_store = get_agent_store()
        self._plugin_store = get_plugin_store()
        self._pricing = get_pricing_engine()
        self._revenue = get_revenue_share()

    # Agent Marketplace
    async def list_agent_marketplace(
        self, category: str = "", search: str = "", sort_by: str = "newest",
        limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        return await self._agent_store.list_marketplace(
            category=category or None, search=search, sort_by=sort_by,
            limit=limit, offset=offset,
        )

    async def get_featured_agents(self) -> List[Dict[str, Any]]:
        return await self._agent_store.get_featured()

    async def search_agents(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        return await self._agent_store.search(query, limit)

    async def get_agent_categories(self) -> List[str]:
        return await self._agent_store.get_categories()

    async def list_agent(self, agent_id: str, tenant_id: str, ctx: Optional[ServiceContext] = None) -> Dict[str, Any]:
        listing = await self._agent_store.list_agent(agent_id, tenant_id, ctx=ctx)
        return listing.to_dict()

    # Plugin Marketplace
    async def list_plugin_marketplace(
        self, category: str = "", search: str = "", sort_by: str = "newest",
        limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        return await self._plugin_store.list_plugins(
            category=category or None, search=search, sort_by=sort_by,
            limit=limit, offset=offset,
        )

    async def get_plugin_categories(self) -> List[str]:
        return await self._plugin_store.get_categories()

    async def list_plugin_listing(
        self, plugin_id: str, tenant_id: str, ctx: Optional[ServiceContext] = None
    ) -> Dict[str, Any]:
        listing = await self._plugin_store.list_plugin(plugin_id, tenant_id, ctx=ctx)
        return listing.to_dict()

    # Revenue
    async def get_revenue_summary(self, tenant_id: str) -> Dict[str, Any]:
        return await self._revenue.get_total_revenue(tenant_id)

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "service": "MarketplaceService",
        }


_marketplace_service: Optional[MarketplaceService] = None


def get_marketplace_service() -> MarketplaceService:
    global _marketplace_service
    if _marketplace_service is None:
        _marketplace_service = MarketplaceService()
    return _marketplace_service