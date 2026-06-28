"""
Agent OS V6.0 - Pricing Engine
Dynamic pricing strategies, tier calculation, discount management
"""
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from agent_os.core_platform.base import BaseService, ServiceContext
from agent_os.config import get_config


class PricingStrategy(str, Enum):
    FLAT = "flat"
    TIERED = "tiered"
    VOLUME = "volume"
    DYNAMIC = "dynamic"
    FREEMIUM = "freemium"


@dataclass
class PriceTier:
    tier_name: str = ""
    min_usage: int = 0
    max_usage: int = -1
    unit_price: float = 0.0
    flat_fee: float = 0.0

    def to_dict(self) -> dict:
        return {
            "tier_name": self.tier_name, "min_usage": self.min_usage,
            "max_usage": self.max_usage, "unit_price": self.unit_price,
            "flat_fee": self.flat_fee,
        }


@dataclass
class PricingPlan:
    plan_id: str = ""
    name: str = ""
    strategy: str = PricingStrategy.FLAT.value
    base_price: float = 0.0
    currency: str = "USD"
    billing_period: str = "monthly"
    tiers: List[PriceTier] = field(default_factory=list)
    discounts: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id, "name": self.name,
            "strategy": self.strategy, "base_price": self.base_price,
            "currency": self.currency, "billing_period": self.billing_period,
            "tiers": [t.to_dict() for t in self.tiers],
            "discounts": self.discounts,
        }


class PricingEngine(BaseService):
    """Pricing Engine: calculate costs for agents, plugins, and usage"""

    def __init__(self):
        super().__init__()
        self._plans: Dict[str, PricingPlan] = {}

    async def create_plan(self, plan: PricingPlan) -> PricingPlan:
        self._plans[plan.plan_id] = plan
        return plan

    async def get_plan(self, plan_id: str) -> PricingPlan:
        from agent_os.core_platform.exceptions import NotFoundException
        plan = self._plans.get(plan_id)
        if not plan:
            raise NotFoundException("PricingPlan", plan_id)
        return plan

    async def calculate_price(
        self, plan_id: str, usage_units: int = 0,
        ctx: Optional[ServiceContext] = None
    ) -> Dict[str, Any]:
        plan = await self.get_plan(plan_id)
        total = plan.base_price

        if plan.strategy == PricingStrategy.TIERED.value and plan.tiers:
            for tier in plan.tiers:
                if tier.min_usage <= usage_units and (tier.max_usage == -1 or usage_units <= tier.max_usage):
                    total = tier.flat_fee + (usage_units * tier.unit_price)
                    break

        elif plan.strategy == PricingStrategy.VOLUME.value:
            total = usage_units * plan.base_price

        # Apply discounts
        for discount in plan.discounts:
            if discount.get("type") == "percentage":
                total *= (1 - discount.get("value", 0) / 100)
            elif discount.get("type") == "fixed":
                total -= discount.get("value", 0)

        return {
            "plan_id": plan_id,
            "usage_units": usage_units,
            "base_price": plan.base_price,
            "total": max(0, total),
            "currency": plan.currency,
            "strategy": plan.strategy,
        }

    async def calculate_agent_price(
        self, agent_pricing: Dict[str, Any], calls: int = 0,
        ctx: Optional[ServiceContext] = None
    ) -> float:
        """Calculate agent execution cost"""
        model = agent_pricing.get("price_model", "free")
        price = agent_pricing.get("price", 0.0)

        if model == "free":
            return 0.0
        elif model == "per_call":
            return price * max(0, calls)
        elif model == "subscription":
            return price
        elif model == "usage_based":
            return price * calls
        return price

    async def calculate_platform_fee(self, amount: float) -> float:
        """Calculate platform fee"""
        cfg = get_config().billing
        return amount * (cfg.platform_fee_percent / 100.0)

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "service": "PricingEngine",
            "total_plans": len(self._plans),
        }


_pricing_engine: Optional[PricingEngine] = None


def get_pricing_engine() -> PricingEngine:
    global _pricing_engine
    if _pricing_engine is None:
        _pricing_engine = PricingEngine()
    return _pricing_engine