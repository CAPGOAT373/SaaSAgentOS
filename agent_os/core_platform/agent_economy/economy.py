"""
Agent OS V6.0 - Agent Economy System
Agent as an Asset: trading, licensing, pricing, ownership
"""
import uuid
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from agent_os.core_platform.base import BaseService, ServiceContext
from agent_os.core_platform.event_bus import EventTypes
from agent_os.core_platform.exceptions import NotFoundException, ValidationException


class PriceModel(str, Enum):
    FREE = "free"
    SUBSCRIPTION = "subscription"
    PER_CALL = "per_call"
    REVENUE_SHARE = "revenue_share"
    ONE_TIME = "one_time"
    USAGE_BASED = "usage_based"


class LicenseType(str, Enum):
    OPEN_SOURCE = "open_source"
    COMMERCIAL = "commercial"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


class AgentStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PUBLISHED = "published"
    SUSPENDED = "suspended"
    DEPRECATED = "deprecated"


@dataclass
class AgentPricing:
    price_model: str = PriceModel.FREE.value
    price: float = 0.0
    currency: str = "USD"
    subscription_interval: str = "monthly"
    free_calls_per_month: int = 100
    per_call_price: float = 0.0
    revenue_share_percent: float = 0.0
    trial_days: int = 0
    custom_pricing: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "price_model": self.price_model, "price": self.price,
            "currency": self.currency, "subscription_interval": self.subscription_interval,
            "free_calls_per_month": self.free_calls_per_month,
            "per_call_price": self.per_call_price,
            "revenue_share_percent": self.revenue_share_percent,
            "trial_days": self.trial_days, "custom_pricing": self.custom_pricing,
        }


@dataclass
class AgentLicense:
    license_type: str = LicenseType.COMMERCIAL.value
    terms: str = ""
    restrictions: List[str] = field(default_factory=list)
    allowed_usage: List[str] = field(default_factory=list)
    commercial_use: bool = True
    redistribution: bool = False
    custom_terms: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "license_type": self.license_type, "terms": self.terms,
            "restrictions": self.restrictions, "allowed_usage": self.allowed_usage,
            "commercial_use": self.commercial_use, "redistribution": self.redistribution,
            "custom_terms": self.custom_terms,
        }


@dataclass
class AgentAsset:
    agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    owner_id: str = ""
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    status: str = AgentStatus.DRAFT.value
    pricing: AgentPricing = field(default_factory=AgentPricing)
    license: AgentLicense = field(default_factory=AgentLicense)
    tags: List[str] = field(default_factory=list)
    category: str = ""
    documentation_url: str = ""
    avatar_url: str = ""
    total_purchases: int = 0
    total_revenue: float = 0.0
    rating: float = 0.0
    review_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id, "tenant_id": self.tenant_id,
            "owner_id": self.owner_id, "name": self.name,
            "description": self.description, "version": self.version,
            "status": self.status, "pricing": self.pricing.to_dict(),
            "license": self.license.to_dict(), "tags": self.tags,
            "category": self.category, "documentation_url": self.documentation_url,
            "total_purchases": self.total_purchases, "total_revenue": self.total_revenue,
            "rating": self.rating, "review_count": self.review_count,
            "created_at": self.created_at, "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


@dataclass
class AgentReview:
    review_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    tenant_id: str = ""
    user_id: str = ""
    rating: int = 5
    comment: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "review_id": self.review_id, "agent_id": self.agent_id,
            "tenant_id": self.tenant_id, "user_id": self.user_id,
            "rating": self.rating, "comment": self.comment, "created_at": self.created_at,
        }


class AgentEconomy(BaseService):
    """Agent Economy System: trading, licensing, pricing, ownership management"""

    def __init__(self):
        super().__init__()
        self._agents: Dict[str, AgentAsset] = {}
        self._reviews: Dict[str, List[AgentReview]] = {}
        self._purchases: List[Dict[str, Any]] = []

    async def register_agent(
        self, tenant_id: str, owner_id: str, name: str, description: str,
        pricing: AgentPricing, license_info: AgentLicense,
        tags: Optional[List[str]] = None, category: str = "",
        ctx: Optional[ServiceContext] = None
    ) -> AgentAsset:
        agent = AgentAsset(
            tenant_id=tenant_id, owner_id=owner_id, name=name,
            description=description, pricing=pricing, license=license_info,
            tags=tags or [], category=category,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._agents[agent.agent_id] = agent
        await self.emit_event(EventTypes.AGENT_CREATED, agent.to_dict(), ctx)
        return agent

    async def get_agent(self, agent_id: str) -> AgentAsset:
        agent = self._agents.get(agent_id)
        if not agent:
            raise NotFoundException("Agent", agent_id)
        return agent

    async def list_agents(
        self, tenant_id: Optional[str] = None, status: Optional[str] = None,
        category: Optional[str] = None, tags: Optional[List[str]] = None,
        limit: int = 50, offset: int = 0
    ) -> List[AgentAsset]:
        agents = list(self._agents.values())
        if tenant_id:
            agents = [a for a in agents if a.tenant_id == tenant_id]
        if status:
            agents = [a for a in agents if a.status == status]
        if category:
            agents = [a for a in agents if a.category == category]
        if tags:
            agents = [a for a in agents if any(t in a.tags for t in tags)]
        return agents[offset:offset + limit]

    async def publish_agent(self, agent_id: str, ctx: Optional[ServiceContext] = None) -> AgentAsset:
        agent = await self.get_agent(agent_id)
        agent.status = AgentStatus.PUBLISHED.value
        agent.updated_at = datetime.now(timezone.utc).isoformat()
        await self.emit_event(EventTypes.AGENT_PUBLISHED, agent.to_dict(), ctx)
        return agent

    async def purchase_agent(
        self, agent_id: str, buyer_tenant_id: str, buyer_user_id: str,
        ctx: Optional[ServiceContext] = None
    ) -> Dict[str, Any]:
        agent = await self.get_agent(agent_id)
        if agent.status != AgentStatus.PUBLISHED.value:
            raise ValidationException(f"Agent {agent_id} is not published")

        amount = agent.pricing.price
        if agent.pricing.price_model == PriceModel.PER_CALL.value:
            amount = agent.pricing.per_call_price

        purchase = {
            "purchase_id": str(uuid.uuid4()),
            "agent_id": agent_id,
            "buyer_tenant_id": buyer_tenant_id,
            "buyer_user_id": buyer_user_id,
            "amount": amount,
            "currency": agent.pricing.currency,
            "purchased_at": datetime.now(timezone.utc).isoformat(),
        }
        self._purchases.append(purchase)

        agent.total_purchases += 1
        agent.total_revenue += amount

        # Distribute revenue through billing engine
        from agent_os.core_platform.billing_engine import get_billing_engine
        billing = get_billing_engine()
        await billing.distribute_agent_revenue(
            transaction_id=purchase["purchase_id"],
            buyer_tenant_id=buyer_tenant_id,
            seller_tenant_id=agent.tenant_id,
            total_amount=amount,
            ctx=ctx,
        )

        await self.emit_event(EventTypes.MARKETPLACE_PURCHASE_COMPLETED, purchase, ctx)
        return purchase

    async def add_review(
        self, agent_id: str, tenant_id: str, user_id: str,
        rating: int, comment: str, ctx: Optional[ServiceContext] = None
    ) -> AgentReview:
        review = AgentReview(
            agent_id=agent_id, tenant_id=tenant_id,
            user_id=user_id, rating=rating, comment=comment,
        )
        if agent_id not in self._reviews:
            self._reviews[agent_id] = []
        self._reviews[agent_id].append(review)

        agent = await self.get_agent(agent_id)
        all_reviews = self._reviews[agent_id]
        agent.rating = sum(r.rating for r in all_reviews) / len(all_reviews)
        agent.review_count = len(all_reviews)

        await self.emit_event(EventTypes.MARKETPLACE_REVIEW_ADDED, review.to_dict(), ctx)
        return review

    async def get_reviews(self, agent_id: str) -> List[AgentReview]:
        return self._reviews.get(agent_id, [])

    async def update_pricing(
        self, agent_id: str, pricing: AgentPricing, ctx: Optional[ServiceContext] = None
    ) -> AgentAsset:
        agent = await self.get_agent(agent_id)
        agent.pricing = pricing
        agent.updated_at = datetime.now(timezone.utc).isoformat()
        await self.emit_event(EventTypes.AGENT_UPDATED, agent.to_dict(), ctx)
        return agent

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "service": "AgentEconomy",
            "total_agents": len(self._agents),
            "total_purchases": len(self._purchases),
        }


_agent_economy: Optional[AgentEconomy] = None


def get_agent_economy() -> AgentEconomy:
    global _agent_economy
    if _agent_economy is None:
        _agent_economy = AgentEconomy()
    return _agent_economy