"""
Agent OS V6.0 - Billing Service
Billing API, usage tracking, subscription management
"""
from typing import Optional, Dict, Any, List
from agent_os.core_platform.billing_engine import (
    get_billing_engine, BillingEngine, Subscription, Invoice, CreditBalance, BillingPeriod
)
from agent_os.core_platform.base import BaseService, ServiceContext


class BillingService(BaseService):
    """Billing Service: subscription management, usage tracking, invoices"""

    def __init__(self):
        super().__init__()
        self._engine = get_billing_engine()

    async def create_subscription(
        self, tenant_id: str, tier: str, period: str = "monthly",
        ctx: Optional[ServiceContext] = None
    ) -> Dict[str, Any]:
        sub = await self._engine.create_subscription(tenant_id, tier, period, ctx)
        return sub.to_dict()

    async def get_subscription(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        sub = await self._engine.get_subscription(tenant_id)
        return sub.to_dict() if sub else None

    async def get_balance(self, tenant_id: str) -> Dict[str, Any]:
        balance = await self._engine.get_balance(tenant_id)
        return balance.to_dict()

    async def record_usage(
        self, tenant_id: str, resource_type: str, resource_id: str,
        amount: float, metadata: Optional[Dict] = None,
        ctx: Optional[ServiceContext] = None
    ) -> Dict[str, Any]:
        return await self._engine.record_usage(
            tenant_id=tenant_id, resource_type=resource_type,
            resource_id=resource_id, amount=amount, metadata=metadata, ctx=ctx,
        )

    async def add_credits(
        self, tenant_id: str, amount: float, description: str = "",
        ctx: Optional[ServiceContext] = None
    ) -> Dict[str, Any]:
        balance = await self._engine.add_credits(tenant_id, amount, description, ctx)
        return balance.to_dict()

    async def create_invoice(
        self, tenant_id: str, amount: float, items: List[Dict[str, Any]],
        ctx: Optional[ServiceContext] = None
    ) -> Dict[str, Any]:
        invoice = await self._engine.create_invoice(tenant_id, amount, items, ctx)
        return invoice.to_dict()

    async def pay_invoice(self, invoice_id: str, ctx: Optional[ServiceContext] = None) -> Dict[str, Any]:
        invoice = await self._engine.pay_invoice(invoice_id, ctx)
        return invoice.to_dict()

    async def get_revenue_report(self, tenant_id: str) -> Dict[str, Any]:
        return await self._engine.get_revenue_report(tenant_id)

    async def get_usage_records(self, tenant_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        return await self._engine.get_usage_records(tenant_id, limit)

    async def health_check(self) -> Dict[str, Any]:
        return await self._engine.health_check()


_billing_service: Optional[BillingService] = None


def get_billing_service() -> BillingService:
    global _billing_service
    if _billing_service is None:
        _billing_service = BillingService()
    return _billing_service