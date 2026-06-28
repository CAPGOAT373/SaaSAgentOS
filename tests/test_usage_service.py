"""
Agent OS V6.0 - UsageService Tests
Unit + Integration tests (UsageService is standalone, no external dependencies)
"""
import pytest
import uuid

from agent_os.core_platform.exceptions import NotFoundException
from agent_os.services.usage_service.service import (
    UsageService, UsageRecord, UsageSummary, get_usage_service,
)


# ============================================================
# Unit Tests (Real UsageService, isolated)
# ============================================================

class TestUsageServiceUnit:
    """Unit tests for UsageService (standalone service)."""

    @pytest.fixture
    def svc(self, isolated_usage_service):
        return isolated_usage_service

    # ── track_usage ───────────────────────────────────

    @pytest.mark.asyncio
    async def test_track_usage_basic(self, svc, service_context):
        record = await svc.track_usage(
            "tenant-001", "agent", "agent-001", "execute",
            quantity=1, cost=0.05, user_id="user-001",
            ctx=service_context,
        )

        assert record.tenant_id == "tenant-001"
        assert record.resource_type == "agent"
        assert record.resource_id == "agent-001"
        assert record.action == "execute"
        assert record.quantity == 1
        assert record.cost == 0.05
        assert record.user_id == "user-001"
        assert record.record_id  # auto-generated

    @pytest.mark.asyncio
    async def test_track_usage_defaults(self, svc, service_context):
        record = await svc.track_usage(
            "tenant-001", "api", "endpoint-1", "call",
            ctx=service_context,
        )

        assert record.quantity == 1
        assert record.cost == 0.0
        assert record.user_id == ""

    @pytest.mark.asyncio
    async def test_track_usage_with_metadata(self, svc, service_context):
        record = await svc.track_usage(
            "tenant-001", "workflow", "wf-001", "run",
            metadata={"step": "init", "duration_ms": 150},
            ctx=service_context,
        )

        assert record.metadata["step"] == "init"
        assert record.metadata["duration_ms"] == 150

    @pytest.mark.asyncio
    async def test_track_usage_multiple(self, svc, service_context):
        for i in range(5):
            await svc.track_usage(
                "tenant-001", "agent", f"agent-{i}", "execute",
                quantity=1, cost=0.01, ctx=service_context,
            )

        assert len(svc._records) == 5

    # ── get_usage ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_usage_by_tenant(self, svc, service_context):
        await svc.track_usage("tenant-A", "agent", "a1", "execute", ctx=service_context)
        await svc.track_usage("tenant-A", "agent", "a2", "execute", ctx=service_context)
        await svc.track_usage("tenant-B", "agent", "a3", "execute", ctx=service_context)

        records = await svc.get_usage("tenant-A")
        assert len(records) == 2

    @pytest.mark.asyncio
    async def test_get_usage_by_resource_type(self, svc, service_context):
        await svc.track_usage("tenant-001", "agent", "a1", "execute", ctx=service_context)
        await svc.track_usage("tenant-001", "plugin", "p1", "run", ctx=service_context)
        await svc.track_usage("tenant-001", "agent", "a2", "execute", ctx=service_context)

        agent_records = await svc.get_usage("tenant-001", resource_type="agent")
        assert len(agent_records) == 2

        plugin_records = await svc.get_usage("tenant-001", resource_type="plugin")
        assert len(plugin_records) == 1

    @pytest.mark.asyncio
    async def test_get_usage_pagination(self, svc, service_context):
        for i in range(10):
            await svc.track_usage("tenant-001", "agent", f"a{i}", "execute", ctx=service_context)

        records = await svc.get_usage("tenant-001", limit=3, offset=2)
        assert len(records) == 3

    @pytest.mark.asyncio
    async def test_get_usage_empty_tenant(self, svc):
        records = await svc.get_usage("nonexistent")
        assert records == []

    # ── get_usage_summary ─────────────────────────────

    @pytest.mark.asyncio
    async def test_get_usage_summary(self, svc, service_context):
        await svc.track_usage("tenant-001", "agent", "a1", "execute", quantity=3, cost=0.15, ctx=service_context)
        await svc.track_usage("tenant-001", "plugin", "p1", "run", quantity=2, cost=0.10, ctx=service_context)
        await svc.track_usage("tenant-001", "workflow", "w1", "run", quantity=1, cost=0.05, ctx=service_context)
        await svc.track_usage("tenant-001", "api", "endpoint", "call", quantity=5, cost=0.01, ctx=service_context)

        summary = await svc.get_usage_summary("tenant-001")

        assert summary.tenant_id == "tenant-001"
        assert summary.total_calls == 11  # 3+2+1+5
        assert summary.total_cost == 0.31  # 0.15+0.10+0.05+0.01
        assert summary.agent_executions == 3
        assert summary.plugin_executions == 2
        assert summary.workflow_executions == 1
        assert summary.api_calls == 5

    @pytest.mark.asyncio
    async def test_get_usage_summary_empty(self, svc):
        summary = await svc.get_usage_summary("empty-tenant")
        assert summary.total_calls == 0
        assert summary.total_cost == 0.0

    # ── quota management ──────────────────────────────

    @pytest.mark.asyncio
    async def test_set_and_check_quota(self, svc, service_context):
        await svc.set_quota("tenant-001", "agent", 100)

        # Use some quota
        await svc.track_usage("tenant-001", "agent", "a1", "execute", quantity=30, ctx=service_context)

        result = await svc.check_quota("tenant-001", "agent")
        assert result["max_quota"] == 100
        assert result["current_usage"] == 30
        assert result["remaining"] == 70

    @pytest.mark.asyncio
    async def test_check_quota_unlimited(self, svc):
        result = await svc.check_quota("tenant-001", "agent")
        assert result["max_quota"] == "unlimited"
        assert result["remaining"] == "unlimited"

    @pytest.mark.asyncio
    async def test_check_quota_exhausted(self, svc, service_context):
        await svc.set_quota("tenant-001", "agent", 10)
        await svc.track_usage("tenant-001", "agent", "a1", "execute", quantity=10, ctx=service_context)

        result = await svc.check_quota("tenant-001", "agent")
        assert result["remaining"] == 0

    @pytest.mark.asyncio
    async def test_set_quota_multiple_resources(self, svc):
        await svc.set_quota("tenant-001", "agent", 100)
        await svc.set_quota("tenant-001", "workflow", 50)
        await svc.set_quota("tenant-001", "api", 1000)

        assert svc._quotas["tenant-001"]["agent"] == 100
        assert svc._quotas["tenant-001"]["workflow"] == 50
        assert svc._quotas["tenant-001"]["api"] == 1000

    # ── get_tenant_analytics ──────────────────────────

    @pytest.mark.asyncio
    async def test_get_tenant_analytics(self, svc, service_context):
        await svc.track_usage("tenant-001", "agent", "a1", "execute", quantity=5, cost=0.25, ctx=service_context)
        await svc.track_usage("tenant-001", "agent", "a2", "execute", quantity=3, cost=0.15, ctx=service_context)
        await svc.track_usage("tenant-001", "plugin", "p1", "run", quantity=2, cost=0.10, ctx=service_context)

        analytics = await svc.get_tenant_analytics("tenant-001")

        assert analytics["tenant_id"] == "tenant-001"
        assert analytics["total_records"] == 3
        assert analytics["summary"]["total_calls"] == 10
        assert analytics["summary"]["total_cost"] == 0.50
        assert analytics["resource_breakdown"]["agent"] == 8
        assert analytics["resource_breakdown"]["plugin"] == 2

    @pytest.mark.asyncio
    async def test_get_tenant_analytics_empty(self, svc):
        analytics = await svc.get_tenant_analytics("empty-tenant")
        assert analytics["total_records"] == 0
        assert analytics["summary"]["total_calls"] == 0

    # ── health_check ──────────────────────────────────

    @pytest.mark.asyncio
    async def test_health_check(self, svc, service_context):
        await svc.track_usage("tenant-001", "agent", "a1", "execute", ctx=service_context)

        result = await svc.health_check()
        assert result["status"] == "healthy"
        assert result["service"] == "UsageService"
        assert result["total_records"] == 1

    # ── UsageRecord dataclass ─────────────────────────

    def test_usage_record_to_dict(self):
        record = UsageRecord(
            tenant_id="t1", user_id="u1", resource_type="agent",
            resource_id="a1", action="execute", quantity=5, cost=0.25,
            region="us-east-1",
        )
        d = record.to_dict()
        assert d["tenant_id"] == "t1"
        assert d["quantity"] == 5
        assert d["cost"] == 0.25
        assert d["region"] == "us-east-1"

    # ── UsageSummary dataclass ────────────────────────

    def test_usage_summary_to_dict(self):
        summary = UsageSummary(
            tenant_id="t1", period="daily", total_calls=100,
            total_cost=50.0, agent_executions=60, plugin_executions=20,
            workflow_executions=10, api_calls=10,
        )
        d = summary.to_dict()
        assert d["tenant_id"] == "t1"
        assert d["total_calls"] == 100
        assert d["total_cost"] == 50.0
        assert d["agent_executions"] == 60

    # ── singleton ─────────────────────────────────────

    def test_singleton(self):
        svc1 = get_usage_service()
        svc2 = get_usage_service()
        assert svc1 is svc2