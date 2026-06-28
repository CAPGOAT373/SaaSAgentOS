"""
Agent OS V6.0 - Test Fixtures & Infrastructure
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict, Any, Optional

from agent_os.config import AppConfig, set_config, get_config
from agent_os.core_platform.base import ServiceContext, BaseService


@pytest.fixture(autouse=True)
def reset_config():
    """Reset config to defaults before each test."""
    config = AppConfig()
    set_config(config)
    yield config


@pytest.fixture
def service_context():
    """Create a test service context."""
    return ServiceContext(
        request_id="test-request-001",
        trace_id="test-trace-001",
        tenant_id="test-tenant",
        user_id="test-user",
    )


@pytest.fixture
def mock_iam():
    """Mock IAMService for AuthService tests."""
    from agent_os.core_platform.identity.iam import Identity, IAMService

    mock = MagicMock(spec=IAMService)
    mock.create_identity = AsyncMock()
    mock.authenticate = AsyncMock()
    mock.decode_jwt = MagicMock()
    mock.get_identity = AsyncMock()
    mock.create_api_key = AsyncMock()
    mock.health_check = AsyncMock()
    return mock


@pytest.fixture
def mock_billing_engine():
    """Mock BillingEngine for BillingService tests."""
    from agent_os.core_platform.billing_engine.engine import (
        BillingEngine, Subscription, Invoice, CreditBalance
    )

    mock = MagicMock(spec=BillingEngine)
    mock.create_subscription = AsyncMock()
    mock.get_subscription = AsyncMock()
    mock.get_balance = AsyncMock()
    mock.record_usage = AsyncMock()
    mock.add_credits = AsyncMock()
    mock.create_invoice = AsyncMock()
    mock.pay_invoice = AsyncMock()
    mock.get_revenue_report = AsyncMock()
    mock.get_usage_records = AsyncMock()
    mock.health_check = AsyncMock()
    return mock


@pytest.fixture
def mock_agent_economy():
    """Mock AgentEconomy for AgentService tests."""
    from agent_os.core_platform.agent_economy.economy import AgentEconomy

    mock = MagicMock(spec=AgentEconomy)
    mock.register_agent = AsyncMock()
    mock.get_agent = AsyncMock()
    mock.list_agents = AsyncMock()
    mock.publish_agent = AsyncMock()
    mock.purchase_agent = AsyncMock()
    mock.add_review = AsyncMock()
    mock.get_reviews = AsyncMock()
    mock.update_pricing = AsyncMock()
    mock.health_check = AsyncMock()
    return mock


@pytest.fixture
def mock_agent_runtime():
    """Mock AgentRuntimeV3 for AgentService tests."""
    from agent_os.ai_layer.agent_runtime_v3.runtime import AgentRuntimeV3

    mock = MagicMock(spec=AgentRuntimeV3)
    mock.create_agent = AsyncMock()
    mock.get_agent = AsyncMock()
    mock.list_agents = AsyncMock()
    mock.execute_agent = AsyncMock()
    mock.get_execution = AsyncMock()
    mock.list_executions = AsyncMock()
    mock.register_tool = MagicMock()
    mock.list_tools = MagicMock()
    mock.create_collaboration_group = AsyncMock()
    mock.execute_collaboration = AsyncMock()
    mock.health_check = AsyncMock()
    return mock


@pytest.fixture
def mock_agent_store():
    """Mock AgentStore for MarketplaceService tests."""
    mock = MagicMock()
    mock.list_marketplace = AsyncMock()
    mock.get_featured = AsyncMock()
    mock.search = AsyncMock()
    mock.get_categories = AsyncMock()
    mock.list_agent = AsyncMock()
    mock.health_check = AsyncMock()
    return mock


@pytest.fixture
def mock_plugin_store():
    """Mock PluginStore for MarketplaceService tests."""
    mock = MagicMock()
    mock.list_plugins = AsyncMock()
    mock.get_categories = AsyncMock()
    mock.list_plugin = AsyncMock()
    mock.health_check = AsyncMock()
    return mock


@pytest.fixture
def mock_pricing_engine():
    """Mock PricingEngine for MarketplaceService tests."""
    mock = MagicMock()
    mock.calculate_price = AsyncMock()
    mock.calculate_agent_price = AsyncMock()
    mock.calculate_platform_fee = AsyncMock()
    mock.health_check = AsyncMock()
    return mock


@pytest.fixture
def mock_revenue_share():
    """Mock RevenueShareEngine for MarketplaceService tests."""
    mock = MagicMock()
    mock.get_total_revenue = AsyncMock()
    mock.distribute_revenue = AsyncMock()
    mock.health_check = AsyncMock()
    return mock


@pytest.fixture
def isolated_workflow_service():
    """Create an isolated WorkflowService for testing."""
    from agent_os.services.workflow_service.service import WorkflowService
    svc = WorkflowService()
    yield svc


@pytest.fixture
def isolated_usage_service():
    """Create an isolated UsageService for testing."""
    from agent_os.services.usage_service.service import UsageService
    svc = UsageService()
    yield svc


@pytest.fixture
def isolated_billing_engine():
    """Create an isolated BillingEngine for integration tests."""
    from agent_os.core_platform.billing_engine.engine import BillingEngine
    engine = BillingEngine()
    yield engine


@pytest.fixture
def isolated_iam():
    """Create an isolated IAMService for integration tests."""
    from agent_os.core_platform.identity.iam import IAMService
    iam = IAMService()
    yield iam


@pytest.fixture
def isolated_agent_economy():
    """Create an isolated AgentEconomy for integration tests."""
    from agent_os.core_platform.agent_economy.economy import AgentEconomy
    economy = AgentEconomy()
    yield economy


@pytest.fixture
def isolated_agent_runtime():
    """Create an isolated AgentRuntimeV3 for integration tests."""
    from agent_os.ai_layer.agent_runtime_v3.runtime import AgentRuntimeV3
    runtime = AgentRuntimeV3()
    yield runtime