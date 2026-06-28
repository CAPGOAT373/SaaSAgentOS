"""
Agent OS V6.0 - Agent Store (Marketplace)
App Store-like agent marketplace with listing, search, categories
"""
import uuid
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from agent_os.core_platform.base import BaseService, ServiceContext
from agent_os.core_platform.agent_economy import AgentAsset, AgentPricing, AgentReview, PriceModel, get_agent_economy
from agent_os.core_platform.exceptions import NotFoundException, ValidationException


@dataclass
class MarketplaceListing:
    listing_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    tenant_id: str = ""
    featured: bool = False
    promoted: bool = False
    display_order: int = 0
    banner_url: str = ""
    screenshots: List[str] = field(default_factory=list)
    demo_video_url: str = ""
    use_cases: List[str] = field(default_factory=list)
    integrations: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "listing_id": self.listing_id, "agent_id": self.agent_id,
            "tenant_id": self.tenant_id, "featured": self.featured,
            "promoted": self.promoted, "display_order": self.display_order,
            "screenshots": self.screenshots, "demo_video_url": self.demo_video_url,
            "use_cases": self.use_cases, "integrations": self.integrations,
            "created_at": self.created_at,
        }


class AgentStore(BaseService):
    """Agent Store: marketplace for discovering and purchasing agents"""

    def __init__(self):
        super().__init__()
        self._listings: Dict[str, MarketplaceListing] = {}
        self._featured: List[str] = []
        self._categories: Dict[str, List[str]] = {}

    async def list_agent(
        self, agent_id: str, tenant_id: str,
        featured: bool = False, use_cases: Optional[List[str]] = None,
        integrations: Optional[List[str]] = None,
        ctx: Optional[ServiceContext] = None
    ) -> MarketplaceListing:
        economy = get_agent_economy()
        agent = await economy.get_agent(agent_id)

        listing = MarketplaceListing(
            agent_id=agent_id, tenant_id=tenant_id,
            featured=featured, use_cases=use_cases or [],
            integrations=integrations or [],
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._listings[listing.listing_id] = listing

        if featured:
            self._featured.append(listing.listing_id)

        if agent.category:
            if agent.category not in self._categories:
                self._categories[agent.category] = []
            self._categories[agent.category].append(listing.listing_id)

        await self.emit_event("marketplace.listing.created", listing.to_dict(), ctx)
        return listing

    async def get_listing(self, listing_id: str) -> MarketplaceListing:
        listing = self._listings.get(listing_id)
        if not listing:
            raise NotFoundException("MarketplaceListing", listing_id)
        return listing

    async def list_marketplace(
        self, category: Optional[str] = None, featured_only: bool = False,
        search: str = "", sort_by: str = "newest",
        limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        economy = get_agent_economy()
        listings = list(self._listings.values())

        if featured_only:
            listings = [l for l in listings if l.listing_id in self._featured]

        if category:
            cat_listing_ids = self._categories.get(category, [])
            listings = [l for l in listings if l.listing_id in cat_listing_ids]

        results = []
        for listing in listings:
            try:
                agent = await economy.get_agent(listing.agent_id)
                if agent.status == "published":
                    results.append({
                        "listing": listing.to_dict(),
                        "agent": agent.to_dict(),
                    })
            except NotFoundException:
                continue

        if search:
            results = [
                r for r in results
                if search.lower() in r["agent"]["name"].lower()
                or search.lower() in r["agent"]["description"].lower()
            ]

        if sort_by == "rating":
            results.sort(key=lambda r: r["agent"]["rating"], reverse=True)
        elif sort_by == "popular":
            results.sort(key=lambda r: r["agent"]["total_purchases"], reverse=True)
        elif sort_by == "price_low":
            results.sort(key=lambda r: r["agent"]["pricing"]["price"])
        else:  # newest
            results.sort(key=lambda r: r["listing"]["created_at"], reverse=True)

        return results[offset:offset + limit]

    async def get_featured(self) -> List[Dict[str, Any]]:
        return await self.list_marketplace(featured_only=True)

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        return await self.list_marketplace(search=query, limit=limit)

    async def get_categories(self) -> List[str]:
        return list(self._categories.keys())

    async def get_category_agents(self, category: str, limit: int = 50) -> List[Dict[str, Any]]:
        return await self.list_marketplace(category=category, limit=limit)

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "service": "AgentStore",
            "total_listings": len(self._listings),
            "featured": len(self._featured),
            "categories": len(self._categories),
        }


_agent_store: Optional[AgentStore] = None


def get_agent_store() -> AgentStore:
    global _agent_store
    if _agent_store is None:
        _agent_store = AgentStore()
    return _agent_store