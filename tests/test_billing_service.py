"""
Agent OS V6.0 - BillingService Tests
Unit tests with mocked BillingEngine + Integration tests with real engine
"""
import pytest
from unittest.mock import AsyncMock

from agent_os.core_platform.billing_engine.engine import (
    BillingEngine, Subscription, Invoice, CreditBalance, BillingPeriod, InvoiceStatus
)
from agent_os.core_platform.exceptions import NotFoundException
from agent_os.services.billing_service.service import BillingService, get_billing_service


# ============================================================
# Unit Tests (Mocked BillingEngine)
# ============================================================

class TestBillingServiceUnit:
    """Unit tests with mocked BillingEngine."""

    @pytest.fixture
    def billing_svc(self, mock_billing_engine):
        svc = BillingService()
        svc._engine = mock_billing_engine
        return svc

    # ── create_subscription ───────────────────────────

    @pytest.mark.asyncio
    async def test_create_subscription_success(self, billing_svc, mock_billing_engine, service_context):
        sub = Subscription(
            sub_id="sub-001", tenant_id="test-tenant",
            tier="pro", period="monthly", price=49.0,
        )
        mock_billing_engine.create_subscription.return_value = sub

        result = await billing_svc.create_subscription(
            "test-tenant", "pro", "monthly", ctx=service_context,
        )

        assert result["sub_id"] == "sub-001"
        assert result["tier"] == "pro"
        assert result["price"] == 49.0
        mock_billing_engine.create_subscription.assert_called_once_with(
            "test-tenant", "pro", "monthly", service_context,
        )

    @pytest.mark.asyncio
    async def test_create_subscription_free_tier(self, billing_svc, mock_billing_engine, service_context):
        sub = Subscription(
            sub_id="sub-002", tenant_id="test-tenant",
            tier="free", period="monthly", price=0.0,
        )
        mock_billing_engine.create_subscription.return_value = sub

        result = await billing_svc.create_subscription(
            "test-tenant", "free", ctx=service_context,
        )

        assert result["tier"] == "free"
        assert result["price"] == 0.0

    # ── get_subscription ──────────────────────────────

    @pytest.mark.asyncio
    async def test_get_subscription_found(self, billing_svc, mock_billing_engine):
        sub = Subscription(
            sub_id="sub-001", tenant_id="test-tenant", tier="pro",
        )
        mock_billing_engine.get_subscription.return_value = sub

        result = await billing_svc.get_subscription("test-tenant")

        assert result["sub_id"] == "sub-001"
        assert result["tier"] == "pro"
        mock_billing_engine.get_subscription.assert_called_once_with("test-tenant")

    @pytest.mark.asyncio
    async def test_get_subscription_none(self, billing_svc, mock_billing_engine):
        mock_billing_engine.get_subscription.return_value = None

        result = await billing_svc.get_subscription("test-tenant")

        assert result is None

    # ── get_balance ───────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_balance(self, billing_svc, mock_billing_engine):
        balance = CreditBalance(
            tenant_id="test-tenant", balance=100.0,
            total_earned=200.0, total_spent=100.0,
        )
        mock_billing_engine.get_balance.return_value = balance

        result = await billing_svc.get_balance("test-tenant")

        assert result["balance"] == 100.0
        assert result["total_earned"] == 200.0
        assert result["total_spent"] == 100.0
        mock_billing_engine.get_balance.assert_called_once_with("test-tenant")

    # ── record_usage ──────────────────────────────────

    @pytest.mark.asyncio
    async def test_record_usage(self, billing_svc, mock_billing_engine, service_context):
        mock_billing_engine.record_usage.return_value = {
            "record_id": "rec-001", "tenant_id": "test-tenant",
            "resource_type": "agent", "amount": 0.05,
        }

        result = await billing_svc.record_usage(
            "test-tenant", "agent", "agent-001", 0.05,
            metadata={"action": "execute"}, ctx=service_context,
        )

        assert result["record_id"] == "rec-001"
        mock_billing_engine.record_usage.assert_called_once_with(
            tenant_id="test-tenant", resource_type="agent",
            resource_id="agent-001", amount=0.05,
            metadata={"action": "execute"}, ctx=service_context,
        )

    # ── add_credits ───────────────────────────────────

    @pytest.mark.asyncio
    async def test_add_credits(self, billing_svc, mock_billing_engine, service_context):
        balance = CreditBalance(
            tenant_id="test-tenant", balance=50.0,
            total_earned=50.0, total_spent=0.0,
        )
        mock_billing_engine.add_credits.return_value = balance

        result = await billing_svc.add_credits(
            "test-tenant", 50.0, "Top-up", ctx=service_context,
        )

        assert result["balance"] == 50.0
        mock_billing_engine.add_credits.assert_called_once_with(
            "test-tenant", 50.0, "Top-up", service_context,
        )

    # ── create_invoice ────────────────────────────────

    @pytest.mark.asyncio
    async def test_create_invoice(self, billing_svc, mock_billing_engine, service_context):
        invoice = Invoice(
            invoice_id="inv-001", tenant_id="test-tenant",
            amount=49.0, status="pending",
        )
        mock_billing_engine.create_invoice.return_value = invoice

        items = [{"description": "Pro subscription", "quantity": 1, "price": 49.0}]
        result = await billing_svc.create_invoice(
            "test-tenant", 49.0, items, ctx=service_context,
        )

        assert result["invoice_id"] == "inv-001"
        assert result["amount"] == 49.0
        assert result["status"] == "pending"
        mock_billing_engine.create_invoice.assert_called_once_with(
            "test-tenant", 49.0, items, service_context,
        )

    # ── pay_invoice ───────────────────────────────────

    @pytest.mark.asyncio
    async def test_pay_invoice(self, billing_svc, mock_billing_engine, service_context):
        invoice = Invoice(
            invoice_id="inv-001", tenant_id="test-tenant",
            amount=49.0, status="paid",
        )
        mock_billing_engine.pay_invoice.return_value = invoice

        result = await billing_svc.pay_invoice("inv-001", ctx=service_context)

        assert result["status"] == "paid"
        mock_billing_engine.pay_invoice.assert_called_once_with(
            "inv-001", service_context,
        )

    # ── get_revenue_report ────────────────────────────

    @pytest.mark.asyncio
    async def test_get_revenue_report(self, billing_svc, mock_billing_engine):
        mock_billing_engine.get_revenue_report.return_value = {
            "tenant_id": "test-tenant", "balance": 500.0,
            "total_earned": 1000.0, "total_spent": 500.0,
        }

        result = await billing_svc.get_revenue_report("test-tenant")

        assert result["balance"] == 500.0
        mock_billing_engine.get_revenue_report.assert_called_once_with("test-tenant")

    # ── get_usage_records ─────────────────────────────

    @pytest.mark.asyncio
    async def test_get_usage_records(self, billing_svc, mock_billing_engine):
        mock_billing_engine.get_usage_records.return_value = [
            {"record_id": "rec-001", "amount": 0.05},
            {"record_id": "rec-002", "amount": 0.10},
        ]

        result = await billing_svc.get_usage_records("test-tenant", limit=50)

        assert len(result) == 2
        mock_billing_engine.get_usage_records.assert_called_once_with("test-tenant", 50)


# ============================================================
# Integration Tests (Real BillingEngine)
# ============================================================

class TestBillingServiceIntegration:
    """Integration tests with real BillingEngine."""

    @pytest.fixture
    def billing_svc(self, isolated_billing_engine):
        svc = BillingService()
        svc._engine = isolated_billing_engine
        return svc, isolated_billing_engine

    @pytest.mark.asyncio
    async def test_full_billing_flow(self, billing_svc, service_context):
        svc, engine = billing_svc

        # 1. Create subscription
        sub = await svc.create_subscription("tenant-001", "pro", ctx=service_context)
        assert sub["tier"] == "pro"
        assert sub["tenant_id"] == "tenant-001"

        # 2. Get subscription
        sub2 = await svc.get_subscription("tenant-001")
        assert sub2["sub_id"] == sub["sub_id"]

        # 3. Add credits
        balance = await svc.add_credits("tenant-001", 100.0, "Initial", ctx=service_context)
        assert balance["balance"] == 100.0

        # 4. Get balance
        bal = await svc.get_balance("tenant-001")
        assert bal["balance"] == 100.0

        # 5. Record usage
        usage = await svc.record_usage(
            "tenant-001", "agent", "agent-001", 5.0, ctx=service_context,
        )
        assert usage["amount"] == 5.0

        # 6. Check balance after usage
        bal2 = await svc.get_balance("tenant-001")
        assert bal2["balance"] == 95.0

        # 7. Create invoice
        invoice = await svc.create_invoice(
            "tenant-001", 49.0,
            [{"description": "Pro monthly", "quantity": 1, "price": 49.0}],
            ctx=service_context,
        )
        assert invoice["amount"] == 49.0
        assert invoice["status"] == "pending"

        # 8. Pay invoice
        paid = await svc.pay_invoice(invoice["invoice_id"], ctx=service_context)
        assert paid["status"] == "paid"

    @pytest.mark.asyncio
    async def test_multiple_tenants(self, billing_svc, service_context):
        svc, engine = billing_svc

        await svc.create_subscription("tenant-A", "free", ctx=service_context)
        await svc.create_subscription("tenant-B", "business", ctx=service_context)

        sub_a = await svc.get_subscription("tenant-A")
        sub_b = await svc.get_subscription("tenant-B")

        assert sub_a["tier"] == "free"
        assert sub_b["tier"] == "business"

    @pytest.mark.asyncio
    async def test_revenue_report(self, billing_svc, service_context):
        svc, engine = billing_svc

        await svc.add_credits("tenant-001", 200.0, ctx=service_context)
        await svc.record_usage("tenant-001", "agent", "a1", 50.0, ctx=service_context)

        report = await svc.get_revenue_report("tenant-001")
        assert report["balance"] == 150.0
        assert report["total_earned"] == 200.0
        assert report["total_spent"] == 50.0

    @pytest.mark.asyncio
    async def test_usage_records(self, billing_svc, service_context):
        svc, engine = billing_svc

        await svc.record_usage("tenant-001", "agent", "a1", 1.0, ctx=service_context)
        await svc.record_usage("tenant-001", "agent", "a2", 2.0, ctx=service_context)
        await svc.record_usage("tenant-001", "workflow", "w1", 3.0, ctx=service_context)

        records = await svc.get_usage_records("tenant-001")
        assert len(records) == 3

    @pytest.mark.asyncio
    async def test_singleton(self):
        svc1 = get_billing_service()
        svc2 = get_billing_service()
        assert svc1 is svc2