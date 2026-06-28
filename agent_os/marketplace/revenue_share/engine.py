"""
Agent OS V6.0 - Revenue Share Engine
Automated revenue distribution for agents, plugins, affiliates
"""
import uuid
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from agent_os.core_platform.base import BaseService, ServiceContext
from agent_os.core_platform.billing_engine import get_billing_engine
from agent_os.config import get_config


@dataclass
class RevenueContract:
    contract_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    creator_tenant_id: str = ""
    creator_share: float = 70.0
    platform_share: float = 15.0
    affiliate_share: float = 15.0
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "contract_id": self.contract_id,
            "creator_tenant_id": self.creator_tenant_id,
            "creator_share": self.creator_share,
            "platform_share": self.platform_share,
            "affiliate_share": self.affiliate_share,
            "is_active": self.is_active,
            "created_at": self.created_at,
        }


@dataclass
class PayoutRecord:
    payout_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    amount: float = 0.0
    currency: str = "USD"
    status: str = "pending"
    payout_type: str = "agent_revenue"
    reference_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    processed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "payout_id": self.payout_id, "tenant_id": self.tenant_id,
            "amount": self.amount, "currency": self.currency,
            "status": self.status, "payout_type": self.payout_type,
            "reference_id": self.reference_id, "created_at": self.created_at,
            "processed_at": self.processed_at,
        }


class RevenueShareEngine(BaseService):
    """Revenue Share Engine: manages contracts and automated payouts"""

    def __init__(self):
        super().__init__()
        self._contracts: Dict[str, RevenueContract] = {}
        self._payouts: List[PayoutRecord] = []

    async def create_contract(
        self, creator_tenant_id: str, creator_share: float = 70.0,
        platform_share: float = 15.0, affiliate_share: float = 15.0,
        ctx: Optional[ServiceContext] = None
    ) -> RevenueContract:
        total = creator_share + platform_share + affiliate_share
        if abs(total - 100.0) > 0.01:
            from agent_os.core_platform.exceptions import ValidationException
            raise ValidationException(f"Share percentages must sum to 100, got {total}")

        contract = RevenueContract(
            creator_tenant_id=creator_tenant_id,
            creator_share=creator_share,
            platform_share=platform_share,
            affiliate_share=affiliate_share,
        )
        self._contracts[contract.contract_id] = contract
        return contract

    async def distribute_revenue(
        self, transaction_id: str, buyer_tenant_id: str,
        seller_tenant_id: str, total_amount: float,
        revenue_type: str = "agent", ctx: Optional[ServiceContext] = None
    ) -> Dict[str, Any]:
        billing = get_billing_engine()
        config = get_config().billing

        if revenue_type == "agent":
            shares = config.agent_revenue_share
        else:
            shares = config.plugin_revenue_share

        platform_fee = total_amount * (shares["platform"] / 100.0)
        creator_amount = total_amount * (shares["creator"] / 100.0)
        affiliate_amount = total_amount * (shares.get("affiliate", 0) / 100.0)

        payouts = []

        if creator_amount > 0:
            payout = PayoutRecord(
                tenant_id=seller_tenant_id, amount=creator_amount,
                payout_type=f"{revenue_type}_revenue", reference_id=transaction_id,
            )
            self._payouts.append(payout)
            payouts.append(payout.to_dict())
            await billing.add_credits(seller_tenant_id, creator_amount, f"{revenue_type} revenue", ctx)

        return {
            "transaction_id": transaction_id,
            "total_amount": total_amount,
            "platform_fee": platform_fee,
            "creator_amount": creator_amount,
            "affiliate_amount": affiliate_amount,
            "payouts": payouts,
        }

    async def get_payouts(
        self, tenant_id: str, limit: int = 50
    ) -> List[PayoutRecord]:
        payouts = [p for p in self._payouts if p.tenant_id == tenant_id]
        return sorted(payouts, key=lambda p: p.created_at, reverse=True)[:limit]

    async def get_total_revenue(self, tenant_id: str) -> Dict[str, Any]:
        payouts = [p for p in self._payouts if p.tenant_id == tenant_id]
        total = sum(p.amount for p in payouts)
        return {
            "tenant_id": tenant_id,
            "total_revenue": total,
            "total_payouts": len(payouts),
            "currency": "USD",
        }

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "service": "RevenueShareEngine",
            "total_contracts": len(self._contracts),
            "total_payouts": len(self._payouts),
        }


_revenue_share: Optional[RevenueShareEngine] = None


def get_revenue_share() -> RevenueShareEngine:
    global _revenue_share
    if _revenue_share is None:
        _revenue_share = RevenueShareEngine()
    return _revenue_share