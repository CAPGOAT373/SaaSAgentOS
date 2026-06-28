"""
Agent OS V6.0 - Billing Engine V3
SaaS billing, agent revenue sharing, plugin revenue sharing, platform fee
"""
import uuid
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from agent_os.config import get_config, BillingConfig
from agent_os.core_platform.base import BaseService, ServiceContext
from agent_os.core_platform.event_bus import EventTypes

CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "CNY": "¥", "JPY": "¥", "GBP": "£"}


class BillingPeriod(str, Enum):
    MONTHLY = "monthly"
    ANNUAL = "annual"
    PER_CALL = "per_call"
    ONE_TIME = "one_time"


class InvoiceStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


@dataclass
class Subscription:
    sub_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    tier: str = "free"
    period: str = BillingPeriod.MONTHLY.value
    price: float = 0.0
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str = ""
    is_active: bool = True
    auto_renew: bool = True

    def to_dict(self) -> dict:
        return {
            "sub_id": self.sub_id, "tenant_id": self.tenant_id,
            "tier": self.tier, "period": self.period, "price": self.price,
            "started_at": self.started_at, "expires_at": self.expires_at,
            "is_active": self.is_active, "auto_renew": self.auto_renew,
        }


@dataclass
class Invoice:
    invoice_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    amount: float = 0.0
    currency: str = "USD"
    status: str = InvoiceStatus.PENDING.value
    items: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    paid_at: str = ""

    def to_dict(self) -> dict:
        return {
            "invoice_id": self.invoice_id, "tenant_id": self.tenant_id,
            "amount": self.amount, "currency": self.currency,
            "status": self.status, "items": self.items,
            "created_at": self.created_at, "paid_at": self.paid_at,
        }


@dataclass
class CreditBalance:
    tenant_id: str = ""
    balance: float = 0.0
    currency: str = "USD"
    total_earned: float = 0.0
    total_spent: float = 0.0
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id, "balance": self.balance,
            "currency": self.currency, "total_earned": self.total_earned,
            "total_spent": self.total_spent, "updated_at": self.updated_at,
        }


@dataclass
class RevenueShareEntry:
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    transaction_id: str = ""
    from_tenant_id: str = ""
    to_tenant_id: str = ""
    amount: float = 0.0
    share_type: str = ""  # agent_revenue or plugin_revenue
    share_percent: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id, "transaction_id": self.transaction_id,
            "from_tenant_id": self.from_tenant_id, "to_tenant_id": self.to_tenant_id,
            "amount": self.amount, "share_type": self.share_type,
            "share_percent": self.share_percent, "created_at": self.created_at,
        }


class BillingEngine(BaseService):
    """Billing Engine V3: SaaS billing + agent/plugin revenue sharing"""

    def __init__(self):
        super().__init__()
        self._subscriptions: Dict[str, Subscription] = {}
        self._invoices: Dict[str, Invoice] = {}
        self._credits: Dict[str, CreditBalance] = {}
        self._revenue_shares: List[RevenueShareEntry] = []
        self._usage_records: List[Dict[str, Any]] = []

    def _ensure_credits(self, tenant_id: str) -> CreditBalance:
        if tenant_id not in self._credits:
            self._credits[tenant_id] = CreditBalance(tenant_id=tenant_id)
        return self._credits[tenant_id]

    async def create_subscription(
        self, tenant_id: str, tier: str, period: str = BillingPeriod.MONTHLY.value,
        ctx: Optional[ServiceContext] = None
    ) -> Subscription:
        tier_config = self.config.billing.subscription_tiers.get(tier, {})
        price = tier_config.get("price", 0)

        sub = Subscription(
            tenant_id=tenant_id, tier=tier, period=period, price=price,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self._subscriptions[sub.sub_id] = sub
        self.log("info", f"Subscription created: {sub.sub_id} for {tenant_id}", ctx)
        return sub

    async def get_subscription(self, tenant_id: str) -> Optional[Subscription]:
        for sub in self._subscriptions.values():
            if sub.tenant_id == tenant_id and sub.is_active:
                return sub
        return None

    async def record_usage(
        self, tenant_id: str, resource_type: str, resource_id: str,
        amount: float, metadata: Optional[Dict] = None, ctx: Optional[ServiceContext] = None
    ) -> Dict[str, Any]:
        record = {
            "record_id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "amount": amount,
            "currency": self.config.billing.default_currency,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        self._usage_records.append(record)

        credits = self._ensure_credits(tenant_id)
        credits.total_spent += amount
        credits.balance = credits.total_earned - credits.total_spent
        credits.updated_at = datetime.now(timezone.utc).isoformat()

        await self.emit_event(EventTypes.BILLING_CREDITS_DEDUCTED, {
            "tenant_id": tenant_id, "amount": amount, "resource_type": resource_type,
            "resource_id": resource_id, "balance": credits.balance,
        }, ctx)
        return record

    async def add_credits(
        self, tenant_id: str, amount: float, description: str = "",
        ctx: Optional[ServiceContext] = None
    ) -> CreditBalance:
        credits = self._ensure_credits(tenant_id)
        credits.total_earned += amount
        credits.balance = credits.total_earned - credits.total_spent
        credits.updated_at = datetime.now(timezone.utc).isoformat()
        self.log("info", f"Credits added: {amount} to {tenant_id}, balance: {credits.balance}", ctx)
        return credits

    async def get_balance(self, tenant_id: str) -> CreditBalance:
        return self._ensure_credits(tenant_id)

    async def create_invoice(
        self, tenant_id: str, amount: float, items: List[Dict[str, Any]],
        ctx: Optional[ServiceContext] = None
    ) -> Invoice:
        invoice = Invoice(
            tenant_id=tenant_id, amount=amount, items=items,
            currency=self.config.billing.default_currency,
        )
        self._invoices[invoice.invoice_id] = invoice
        await self.emit_event(EventTypes.BILLING_INVOICE_CREATED, invoice.to_dict(), ctx)
        return invoice

    async def pay_invoice(self, invoice_id: str, ctx: Optional[ServiceContext] = None) -> Invoice:
        invoice = self._invoices.get(invoice_id)
        if not invoice:
            from agent_os.core_platform.exceptions import NotFoundException
            raise NotFoundException("Invoice", invoice_id)
        invoice.status = InvoiceStatus.PAID.value
        invoice.paid_at = datetime.now(timezone.utc).isoformat()
        await self.emit_event(EventTypes.BILLING_PAYMENT_RECEIVED, invoice.to_dict(), ctx)
        return invoice

    async def distribute_agent_revenue(
        self, transaction_id: str, buyer_tenant_id: str, seller_tenant_id: str,
        total_amount: float, ctx: Optional[ServiceContext] = None
    ) -> List[RevenueShareEntry]:
        """Distribute agent revenue according to share ratios"""
        shares = self.config.billing.agent_revenue_share
        entries = []

        platform_fee = total_amount * (shares["platform"] / 100.0)
        creator_share = total_amount * (shares["creator"] / 100.0)
        affiliate_share = total_amount * (shares["affiliate"] / 100.0)

        # Platform fee
        if platform_fee > 0:
            entry = RevenueShareEntry(
                transaction_id=transaction_id, from_tenant_id=buyer_tenant_id,
                to_tenant_id="platform", amount=platform_fee,
                share_type="agent_revenue_platform", share_percent=shares["platform"],
            )
            self._revenue_shares.append(entry)
            entries.append(entry)

        # Creator share
        if creator_share > 0:
            await self.add_credits(seller_tenant_id, creator_share, "Agent revenue share", ctx)
            entry = RevenueShareEntry(
                transaction_id=transaction_id, from_tenant_id=buyer_tenant_id,
                to_tenant_id=seller_tenant_id, amount=creator_share,
                share_type="agent_revenue_creator", share_percent=shares["creator"],
            )
            self._revenue_shares.append(entry)
            entries.append(entry)

        await self.emit_event(EventTypes.BILLING_REVENUE_SHARED, {
            "transaction_id": transaction_id,
            "total_amount": total_amount,
            "entries": [e.to_dict() for e in entries],
        }, ctx)
        return entries

    async def distribute_plugin_revenue(
        self, transaction_id: str, buyer_tenant_id: str, seller_tenant_id: str,
        total_amount: float, ctx: Optional[ServiceContext] = None
    ) -> List[RevenueShareEntry]:
        """Distribute plugin revenue according to share ratios"""
        shares = self.config.billing.plugin_revenue_share
        entries = []

        platform_fee = total_amount * (shares["platform"] / 100.0)
        developer_share = total_amount * (shares["developer"] / 100.0)

        if platform_fee > 0:
            entry = RevenueShareEntry(
                transaction_id=transaction_id, from_tenant_id=buyer_tenant_id,
                to_tenant_id="platform", amount=platform_fee,
                share_type="plugin_revenue_platform", share_percent=shares["platform"],
            )
            self._revenue_shares.append(entry)
            entries.append(entry)

        if developer_share > 0:
            await self.add_credits(seller_tenant_id, developer_share, "Plugin revenue share", ctx)
            entry = RevenueShareEntry(
                transaction_id=transaction_id, from_tenant_id=buyer_tenant_id,
                to_tenant_id=seller_tenant_id, amount=developer_share,
                share_type="plugin_revenue_developer", share_percent=shares["developer"],
            )
            self._revenue_shares.append(entry)
            entries.append(entry)

        await self.emit_event(EventTypes.BILLING_REVENUE_SHARED, {
            "transaction_id": transaction_id,
            "total_amount": total_amount,
            "entries": [e.to_dict() for e in entries],
        }, ctx)
        return entries

    async def get_revenue_report(self, tenant_id: str) -> Dict[str, Any]:
        earned = sum(e.amount for e in self._revenue_shares if e.to_tenant_id == tenant_id)
        credits = self._ensure_credits(tenant_id)
        return {
            "tenant_id": tenant_id,
            "balance": credits.balance,
            "total_earned": credits.total_earned,
            "total_spent": credits.total_spent,
            "currency": credits.currency,
            "revenue_shares": self._revenue_shares,
        }

    async def get_usage_records(self, tenant_id: str, limit: int = 100) -> List[Dict]:
        return [r for r in self._usage_records if r["tenant_id"] == tenant_id][:limit]

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "service": "BillingEngine",
            "subscriptions": len(self._subscriptions),
            "invoices": len(self._invoices),
            "credits_accounts": len(self._credits),
        }


_billing_engine: Optional[BillingEngine] = None


def get_billing_engine() -> BillingEngine:
    global _billing_engine
    if _billing_engine is None:
        _billing_engine = BillingEngine()
    return _billing_engine