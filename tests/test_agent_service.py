"""
Agent OS V6.0 - AgentService Tests
Unit tests with mocked AgentEconomy + AgentRuntimeV3 + Integration tests
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent_os.core_platform.agent_economy.economy import (
    AgentEconomy, AgentAsset, AgentPricing, AgentLicense, AgentReview,
    AgentStatus, PriceModel, LicenseType,
)
from agent_os.ai_layer.agent_runtime_v3.runtime import (
    AgentRuntimeV3, AgentConfig, AgentExecution, AgentExecutionStatus,
    AgentType, ToolDefinition,
)
from agent_os.core_platform.exceptions import NotFoundException, ValidationException
from agent_os.services.agent_service.service import AgentService, get_agent_service


# ============================================================
# Unit Tests (Mocked Dependencies)
# ============================================================

class TestAgentServiceUnit:
    """Unit tests with mocked AgentEconomy and AgentRuntimeV3."""

    @pytest.fixture
    def agent_svc(self, mock_agent_economy, mock_agent_runtime):
        svc = AgentService()
        svc._economy = mock_agent_economy
        svc._runtime = mock_agent_runtime
        return svc

    # ── register_agent ────────────────────────────────

    @pytest.mark.asyncio
    async def test_register_agent_success(self, agent_svc, mock_agent_economy, mock_agent_runtime, service_context):
        asset = AgentAsset(
            agent_id="agent-001", tenant_id="test-tenant", owner_id="owner-001",
            name="MyAgent", description="A test agent", category="chat",
        )
        mock_agent_economy.register_agent.return_value = asset

        result = await agent_svc.register_agent(
            tenant_id="test-tenant", owner_id="owner-001",
            name="MyAgent", description="A test agent",
            agent_type="chat", system_prompt="You are helpful",
            price_model="free", tags=["ai"], category="chat",
            ctx=service_context,
        )

        assert result["agent_id"] == "agent-001"
        assert result["name"] == "MyAgent"
        # Verify economy was called
        assert mock_agent_economy.register_agent.called
        # Verify runtime was called
        assert mock_agent_runtime.create_agent.called

    @pytest.mark.asyncio
    async def test_register_agent_default_system_prompt(self, agent_svc, mock_agent_economy, mock_agent_runtime, service_context):
        asset = AgentAsset(
            agent_id="agent-002", tenant_id="test-tenant", owner_id="owner-001",
            name="Bot", description="",
        )
        mock_agent_economy.register_agent.return_value = asset

        result = await agent_svc.register_agent(
            tenant_id="test-tenant", owner_id="owner-001",
            name="Bot", description="", ctx=service_context,
        )

        assert result["name"] == "Bot"
        # Default system prompt should be auto-generated
        call_args = mock_agent_runtime.create_agent.call_args[0][0]
        assert "You are Bot" in call_args.system_prompt

    @pytest.mark.asyncio
    async def test_register_agent_with_pricing(self, agent_svc, mock_agent_economy, mock_agent_runtime, service_context):
        asset = AgentAsset(
            agent_id="agent-003", tenant_id="test-tenant", owner_id="owner-001",
            name="PremiumAgent", description="Paid agent",
            pricing=AgentPricing(price_model="subscription", price=29.99),
        )
        mock_agent_economy.register_agent.return_value = asset

        result = await agent_svc.register_agent(
            tenant_id="test-tenant", owner_id="owner-001",
            name="PremiumAgent", description="Paid agent",
            price_model="subscription", price=29.99, ctx=service_context,
        )

        assert result["pricing"]["price_model"] == "subscription"
        assert result["pricing"]["price"] == 29.99

    # ── get_agent ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_agent_success(self, agent_svc, mock_agent_economy):
        asset = AgentAsset(
            agent_id="agent-001", tenant_id="test-tenant", name="MyAgent",
        )
        mock_agent_economy.get_agent.return_value = asset

        result = await agent_svc.get_agent("agent-001")

        assert result["agent_id"] == "agent-001"
        assert result["name"] == "MyAgent"
        mock_agent_economy.get_agent.assert_called_once_with("agent-001")

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, agent_svc, mock_agent_economy):
        mock_agent_economy.get_agent.side_effect = NotFoundException("Agent", "agent-999")

        with pytest.raises(NotFoundException, match="Agent not found"):
            await agent_svc.get_agent("agent-999")

    # ── list_agents ───────────────────────────────────

    @pytest.mark.asyncio
    async def test_list_agents(self, agent_svc, mock_agent_economy):
        assets = [
            AgentAsset(agent_id="a1", name="Agent1"),
            AgentAsset(agent_id="a2", name="Agent2"),
        ]
        mock_agent_economy.list_agents.return_value = assets

        result = await agent_svc.list_agents(tenant_id="test-tenant")

        assert len(result) == 2
        assert result[0]["name"] == "Agent1"
        mock_agent_economy.list_agents.assert_called_once_with(
            tenant_id="test-tenant", limit=50, offset=0,
        )

    @pytest.mark.asyncio
    async def test_list_agents_empty(self, agent_svc, mock_agent_economy):
        mock_agent_economy.list_agents.return_value = []

        result = await agent_svc.list_agents()

        assert result == []

    # ── execute_agent ─────────────────────────────────

    @pytest.mark.asyncio
    async def test_execute_agent_success(self, agent_svc, mock_agent_runtime, service_context):
        execution = AgentExecution(
            execution_id="exec-001", agent_id="agent-001",
            status="completed", input="Hello", output="Hi there!",
        )
        mock_agent_runtime.execute_agent.return_value = execution

        result = await agent_svc.execute_agent(
            "agent-001", "Hello", user_id="user-001",
            tenant_id="test-tenant", ctx=service_context,
        )

        assert result["execution_id"] == "exec-001"
        assert result["status"] == "completed"
        assert result["output"] == "Hi there!"
        mock_agent_runtime.execute_agent.assert_called_once_with(
            agent_id="agent-001", user_input="Hello",
            user_id="user-001", tenant_id="test-tenant", ctx=service_context,
        )

    @pytest.mark.asyncio
    async def test_execute_agent_failed(self, agent_svc, mock_agent_runtime, service_context):
        execution = AgentExecution(
            execution_id="exec-002", agent_id="agent-001",
            status="failed", error="LLM timeout",
        )
        mock_agent_runtime.execute_agent.return_value = execution

        result = await agent_svc.execute_agent(
            "agent-001", "Hello", ctx=service_context,
        )

        assert result["status"] == "failed"
        assert result["error"] == "LLM timeout"

    # ── get_execution ─────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_execution(self, agent_svc, mock_agent_runtime):
        execution = AgentExecution(
            execution_id="exec-001", agent_id="agent-001",
        )
        mock_agent_runtime.get_execution.return_value = execution

        result = await agent_svc.get_execution("exec-001")

        assert result["execution_id"] == "exec-001"
        mock_agent_runtime.get_execution.assert_called_once_with("exec-001")

    # ── list_executions ───────────────────────────────

    @pytest.mark.asyncio
    async def test_list_executions(self, agent_svc, mock_agent_runtime):
        executions = [
            AgentExecution(execution_id="e1", agent_id="agent-001"),
            AgentExecution(execution_id="e2", agent_id="agent-001"),
        ]
        mock_agent_runtime.list_executions.return_value = executions

        result = await agent_svc.list_executions("agent-001", limit=10)

        assert len(result) == 2
        mock_agent_runtime.list_executions.assert_called_once_with("agent-001", limit=10)

    # ── add_tool ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_add_tool(self, agent_svc, mock_agent_runtime):
        result = await agent_svc.add_tool(
            name="web_search", description="Search the web",
            parameters={"query": {"type": "string"}},
        )

        assert result["name"] == "web_search"
        assert mock_agent_runtime.register_tool.called

    # ── list_tools ────────────────────────────────────

    @pytest.mark.asyncio
    async def test_list_tools(self, agent_svc, mock_agent_runtime):
        tools = [
            ToolDefinition(name="tool1", description="A tool"),
            ToolDefinition(name="tool2", description="Another tool"),
        ]
        mock_agent_runtime.list_tools.return_value = tools

        result = await agent_svc.list_tools()

        assert len(result) == 2
        assert result[0]["name"] == "tool1"

    # ── publish_agent ─────────────────────────────────

    @pytest.mark.asyncio
    async def test_publish_agent(self, agent_svc, mock_agent_economy, service_context):
        asset = AgentAsset(
            agent_id="agent-001", name="MyAgent", status="published",
        )
        mock_agent_economy.publish_agent.return_value = asset

        result = await agent_svc.publish_agent("agent-001", ctx=service_context)

        assert result["status"] == "published"
        mock_agent_economy.publish_agent.assert_called_once_with("agent-001", service_context)

    # ── purchase_agent ────────────────────────────────

    @pytest.mark.asyncio
    async def test_purchase_agent(self, agent_svc, mock_agent_economy, service_context):
        mock_agent_economy.purchase_agent.return_value = {
            "purchase_id": "purchase-001",
            "agent_id": "agent-001",
            "buyer_tenant_id": "buyer-tenant",
            "amount": 29.99,
        }

        result = await agent_svc.purchase_agent(
            "agent-001", "buyer-tenant", "buyer-user", ctx=service_context,
        )

        assert result["purchase_id"] == "purchase-001"
        assert result["amount"] == 29.99
        mock_agent_economy.purchase_agent.assert_called_once_with(
            agent_id="agent-001", buyer_tenant_id="buyer-tenant",
            buyer_user_id="buyer-user", ctx=service_context,
        )

    # ── add_review ────────────────────────────────────

    @pytest.mark.asyncio
    async def test_add_review(self, agent_svc, mock_agent_economy, service_context):
        review = AgentReview(
            review_id="review-001", agent_id="agent-001",
            tenant_id="test-tenant", user_id="user-001",
            rating=5, comment="Great agent!",
        )
        mock_agent_economy.add_review.return_value = review

        result = await agent_svc.add_review(
            "agent-001", "test-tenant", "user-001",
            rating=5, comment="Great agent!", ctx=service_context,
        )

        assert result["rating"] == 5
        assert result["comment"] == "Great agent!"
        mock_agent_economy.add_review.assert_called_once_with(
            agent_id="agent-001", tenant_id="test-tenant",
            user_id="user-001", rating=5, comment="Great agent!",
            ctx=service_context,
        )

    # ── get_reviews ───────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_reviews(self, agent_svc, mock_agent_economy):
        reviews = [
            AgentReview(review_id="r1", rating=5),
            AgentReview(review_id="r2", rating=4),
        ]
        mock_agent_economy.get_reviews.return_value = reviews

        result = await agent_svc.get_reviews("agent-001")

        assert len(result) == 2
        assert result[0]["rating"] == 5

    # ── health_check ──────────────────────────────────

    @pytest.mark.asyncio
    async def test_health_check(self, agent_svc):
        result = await agent_svc.health_check()

        assert result["status"] == "healthy"
        assert result["service"] == "AgentService"


# ============================================================
# Integration Tests (Real Economy + Runtime)
# ============================================================

class TestAgentServiceIntegration:
    """Integration tests with real AgentEconomy and AgentRuntimeV3."""

    @pytest.fixture
    def agent_svc(self, isolated_agent_economy, isolated_agent_runtime):
        svc = AgentService()
        svc._economy = isolated_agent_economy
        svc._runtime = isolated_agent_runtime
        return svc, isolated_agent_economy, isolated_agent_runtime

    @pytest.mark.asyncio
    async def test_full_agent_lifecycle(self, agent_svc, service_context):
        svc, economy, runtime = agent_svc

        # 1. Register agent
        agent = await svc.register_agent(
            tenant_id="tenant-001", owner_id="owner-001",
            name="LifecycleAgent", description="Testing lifecycle",
            agent_type="chat", price_model="free",
            category="test", ctx=service_context,
        )
        agent_id = agent["agent_id"]
        assert agent["name"] == "LifecycleAgent"
        assert agent["status"] == "draft"

        # 2. Get agent
        fetched = await svc.get_agent(agent_id)
        assert fetched["agent_id"] == agent_id

        # 3. Add tool
        tool = await svc.add_tool(
            name="calculator", description="Calculate",
            parameters={"expression": {"type": "string"}},
        )
        assert tool["name"] == "calculator"

        # 4. List tools
        tools = await svc.list_tools()
        assert len(tools) == 1

        # 5. Publish agent
        published = await svc.publish_agent(agent_id, ctx=service_context)
        assert published["status"] == "published"

        # 6. Add review
        review = await svc.add_review(
            agent_id, "tenant-001", "user-001",
            rating=4, comment="Good", ctx=service_context,
        )
        assert review["rating"] == 4

        # 7. Get reviews
        reviews = await svc.get_reviews(agent_id)
        assert len(reviews) == 1

    @pytest.mark.asyncio
    async def test_list_agents_by_tenant(self, agent_svc, service_context):
        svc, economy, runtime = agent_svc

        await svc.register_agent(
            "tenant-A", "owner-1", "AgentA", "Desc", ctx=service_context,
        )
        await svc.register_agent(
            "tenant-A", "owner-1", "AgentA2", "Desc", ctx=service_context,
        )
        await svc.register_agent(
            "tenant-B", "owner-2", "AgentB", "Desc", ctx=service_context,
        )

        agents_a = await svc.list_agents(tenant_id="tenant-A")
        assert len(agents_a) == 2

        agents_b = await svc.list_agents(tenant_id="tenant-B")
        assert len(agents_b) == 1

    @pytest.mark.asyncio
    async def test_purchase_agent(self, agent_svc, service_context):
        svc, economy, runtime = agent_svc

        agent = await svc.register_agent(
            "seller-tenant", "seller-owner", "SellableAgent", "Desc",
            price_model="one_time", price=9.99, ctx=service_context,
        )
        await svc.publish_agent(agent["agent_id"], ctx=service_context)

        purchase = await svc.purchase_agent(
            agent["agent_id"], "buyer-tenant", "buyer-user",
            ctx=service_context,
        )

        assert purchase["agent_id"] == agent["agent_id"]
        assert purchase["buyer_tenant_id"] == "buyer-tenant"

    @pytest.mark.asyncio
    async def test_purchase_unpublished_agent_fails(self, agent_svc, service_context):
        svc, economy, runtime = agent_svc

        agent = await svc.register_agent(
            "seller-tenant", "seller-owner", "DraftAgent", "Desc",
            ctx=service_context,
        )

        with pytest.raises(ValidationException, match="not published"):
            await svc.purchase_agent(
                agent["agent_id"], "buyer-tenant", "buyer-user",
                ctx=service_context,
            )

    @pytest.mark.asyncio
    async def test_singleton(self):
        svc1 = get_agent_service()
        svc2 = get_agent_service()
        assert svc1 is svc2