"""
Agent OS V6.0 - MarketplaceService Tests
Unit tests with mocked AgentStore, PluginStore, PricingEngine, RevenueShare
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent_os.core_platform.exceptions import NotFoundException
from agent_os.services.marketplace_service.service import (
    MarketplaceService, get_marketplace_service,
)


# ============================================================
# Unit Tests (Mocked Dependencies)
# ============================================================

class TestMarketplaceServiceUnit:
    """Unit tests with mocked AgentStore, PluginStore, PricingEngine, RevenueShare."""

    @pytest.fixture
    def mkt_svc(self, mock_agent_store, mock_plugin_store, mock_pricing_engine, mock_revenue_share):
        svc = MarketplaceService()
        svc._agent_store = mock_agent_store
        svc._plugin_store = mock_plugin_store
        svc._pricing = mock_pricing_engine
        svc._revenue = mock_revenue_share
        return svc

    # ── Agent Marketplace ─────────────────────────────

    @pytest.mark.asyncio
    async def test_list_agent_marketplace(self, mkt_svc, mock_agent_store):
        mock_agent_store.list_marketplace.return_value = [
            {"listing": {"listing_id": "l1"}, "agent": {"name": "Agent1"}},
            {"listing": {"listing_id": "l2"}, "agent": {"name": "Agent2"}},
        ]

        result = await mkt_svc.list_agent_marketplace(
            category="chat", search="agent", sort_by="rating",
            limit=10, offset=0,
        )

        assert len(result) == 2
        assert result[0]["agent"]["name"] == "Agent1"
        mock_agent_store.list_marketplace.assert_called_once_with(
            category="chat", search="agent", sort_by="rating",
            limit=10, offset=0,
        )

    @pytest.mark.asyncio
    async def test_list_agent_marketplace_defaults(self, mkt_svc, mock_agent_store):
        mock_agent_store.list_marketplace.return_value = []

        result = await mkt_svc.list_agent_marketplace()

        assert result == []
        mock_agent_store.list_marketplace.assert_called_once_with(
            category=None, search="", sort_by="newest", limit=50, offset=0,
        )

    @pytest.mark.asyncio
    async def test_list_agent_marketplace_empty(self, mkt_svc, mock_agent_store):
        mock_agent_store.list_marketplace.return_value = []

        result = await mkt_svc.list_agent_marketplace()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_featured_agents(self, mkt_svc, mock_agent_store):
        mock_agent_store.get_featured.return_value = [
            {"listing": {"listing_id": "l1"}, "agent": {"name": "FeaturedAgent"}},
        ]

        result = await mkt_svc.get_featured_agents()

        assert len(result) == 1
        assert result[0]["agent"]["name"] == "FeaturedAgent"
        mock_agent_store.get_featured.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_featured_agents_empty(self, mkt_svc, mock_agent_store):
        mock_agent_store.get_featured.return_value = []

        result = await mkt_svc.get_featured_agents()

        assert result == []

    @pytest.mark.asyncio
    async def test_search_agents(self, mkt_svc, mock_agent_store):
        mock_agent_store.search.return_value = [
            {"listing": {"listing_id": "l1"}, "agent": {"name": "Search Result"}},
        ]

        result = await mkt_svc.search_agents("AI assistant", limit=10)

        assert len(result) == 1
        mock_agent_store.search.assert_called_once_with("AI assistant", 10)

    @pytest.mark.asyncio
    async def test_search_agents_default_limit(self, mkt_svc, mock_agent_store):
        mock_agent_store.search.return_value = []

        await mkt_svc.search_agents("query")

        mock_agent_store.search.assert_called_once_with("query", 20)

    @pytest.mark.asyncio
    async def test_get_agent_categories(self, mkt_svc, mock_agent_store):
        mock_agent_store.get_categories.return_value = ["chat", "coding", "data"]

        result = await mkt_svc.get_agent_categories()

        assert result == ["chat", "coding", "data"]
        mock_agent_store.get_categories.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_agent_categories_empty(self, mkt_svc, mock_agent_store):
        mock_agent_store.get_categories.return_value = []

        result = await mkt_svc.get_agent_categories()

        assert result == []

    @pytest.mark.asyncio
    async def test_list_agent(self, mkt_svc, mock_agent_store, service_context):
        listing = MagicMock()
        listing.to_dict.return_value = {"listing_id": "l1", "agent_id": "agent-001"}
        mock_agent_store.list_agent.return_value = listing

        result = await mkt_svc.list_agent("agent-001", "tenant-001", ctx=service_context)

        assert result["listing_id"] == "l1"
        assert result["agent_id"] == "agent-001"
        mock_agent_store.list_agent.assert_called_once_with(
            "agent-001", "tenant-001", ctx=service_context,
        )

    # ── Plugin Marketplace ────────────────────────────

    @pytest.mark.asyncio
    async def test_list_plugin_marketplace(self, mkt_svc, mock_plugin_store):
        mock_plugin_store.list_plugins.return_value = [
            {"listing": {"listing_id": "pl1"}, "plugin": {"name": "Plugin1"}},
            {"listing": {"listing_id": "pl2"}, "plugin": {"name": "Plugin2"}},
        ]

        result = await mkt_svc.list_plugin_marketplace(
            category="tool", search="plugin", sort_by="popular",
        )

        assert len(result) == 2
        assert result[0]["plugin"]["name"] == "Plugin1"
        mock_plugin_store.list_plugins.assert_called_once_with(
            category="tool", search="plugin", sort_by="popular",
            limit=50, offset=0,
        )

    @pytest.mark.asyncio
    async def test_list_plugin_marketplace_defaults(self, mkt_svc, mock_plugin_store):
        mock_plugin_store.list_plugins.return_value = []

        result = await mkt_svc.list_plugin_marketplace()

        assert result == []
        mock_plugin_store.list_plugins.assert_called_once_with(
            category=None, search="", sort_by="newest", limit=50, offset=0,
        )

    @pytest.mark.asyncio
    async def test_get_plugin_categories(self, mkt_svc, mock_plugin_store):
        mock_plugin_store.get_categories.return_value = ["tool", "connector", "analytics"]

        result = await mkt_svc.get_plugin_categories()

        assert result == ["tool", "connector", "analytics"]
        mock_plugin_store.get_categories.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_plugin_listing(self, mkt_svc, mock_plugin_store, service_context):
        listing = MagicMock()
        listing.to_dict.return_value = {"listing_id": "pl1", "plugin_id": "plugin-001"}
        mock_plugin_store.list_plugin.return_value = listing

        result = await mkt_svc.list_plugin_listing(
            "plugin-001", "tenant-001", ctx=service_context,
        )

        assert result["listing_id"] == "pl1"
        mock_plugin_store.list_plugin.assert_called_once_with(
            "plugin-001", "tenant-001", ctx=service_context,
        )

    # ── Revenue ───────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_revenue_summary(self, mkt_svc, mock_revenue_share):
        mock_revenue_share.get_total_revenue.return_value = {
            "tenant_id": "tenant-001",
            "total_revenue": 1500.0,
            "total_payouts": 25,
            "currency": "USD",
        }

        result = await mkt_svc.get_revenue_summary("tenant-001")

        assert result["total_revenue"] == 1500.0
        assert result["total_payouts"] == 25
        mock_revenue_share.get_total_revenue.assert_called_once_with("tenant-001")

    @pytest.mark.asyncio
    async def test_get_revenue_summary_zero(self, mkt_svc, mock_revenue_share):
        mock_revenue_share.get_total_revenue.return_value = {
            "tenant_id": "tenant-002",
            "total_revenue": 0.0,
            "total_payouts": 0,
        }

        result = await mkt_svc.get_revenue_summary("tenant-002")

        assert result["total_revenue"] == 0.0

    # ── health_check ──────────────────────────────────

    @pytest.mark.asyncio
    async def test_health_check(self, mkt_svc):
        result = await mkt_svc.health_check()

        assert result["status"] == "healthy"
        assert result["service"] == "MarketplaceService"

    # ── singleton ─────────────────────────────────────

    def test_singleton(self):
        svc1 = get_marketplace_service()
        svc2 = get_marketplace_service()
        assert svc1 is svc2


# ============================================================
# Integration Tests (Real Dependencies)
# ============================================================

class TestMarketplaceServiceIntegration:
    """Integration tests with real store dependencies."""

    @pytest.fixture
    def mkt_svc(self):
        svc = MarketplaceService()
        return svc

    @pytest.mark.asyncio
    async def test_agent_marketplace_flow(self, mkt_svc):
        # Initially empty
        agents = await mkt_svc.list_agent_marketplace()
        assert agents == []

        categories = await mkt_svc.get_agent_categories()
        assert categories == []

        featured = await mkt_svc.get_featured_agents()
        assert featured == []

    @pytest.mark.asyncio
    async def test_plugin_marketplace_flow(self, mkt_svc):
        plugins = await mkt_svc.list_plugin_marketplace()
        assert plugins == []

        categories = await mkt_svc.get_plugin_categories()
        assert categories == []

    @pytest.mark.asyncio
    async def test_revenue_summary(self, mkt_svc):
        summary = await mkt_svc.get_revenue_summary("tenant-001")
        assert "total_revenue" in summary
        assert "total_payouts" in summary