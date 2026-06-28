"""
Agent OS V6.0 - Plugin Store (Marketplace)
Plugin marketplace with discovery, installation, versioning
"""
import uuid
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from agent_os.core_platform.base import BaseService, ServiceContext
from agent_os.core_platform.plugin_runtime import PluginAsset, get_plugin_runtime
from agent_os.core_platform.exceptions import NotFoundException


@dataclass
class PluginListing:
    listing_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    plugin_id: str = ""
    tenant_id: str = ""
    featured: bool = False
    verified: bool = False
    display_order: int = 0
    icon_url: str = ""
    screenshots: List[str] = field(default_factory=list)
    documentation_url: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "listing_id": self.listing_id, "plugin_id": self.plugin_id,
            "tenant_id": self.tenant_id, "featured": self.featured,
            "verified": self.verified, "display_order": self.display_order,
            "icon_url": self.icon_url, "screenshots": self.screenshots,
            "documentation_url": self.documentation_url,
            "created_at": self.created_at,
        }


class PluginStore(BaseService):
    """Plugin Store: marketplace for discovering and installing plugins"""

    def __init__(self):
        super().__init__()
        self._listings: Dict[str, PluginListing] = {}
        self._categories: Dict[str, List[str]] = {}

    async def list_plugin(
        self, plugin_id: str, tenant_id: str,
        featured: bool = False, verified: bool = False,
        ctx: Optional[ServiceContext] = None
    ) -> PluginListing:
        runtime = get_plugin_runtime()
        plugin = await runtime.get_plugin(plugin_id)

        listing = PluginListing(
            plugin_id=plugin_id, tenant_id=tenant_id,
            featured=featured, verified=verified,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._listings[listing.listing_id] = listing

        if plugin.category:
            if plugin.category not in self._categories:
                self._categories[plugin.category] = []
            self._categories[plugin.category].append(listing.listing_id)

        return listing

    async def get_listing(self, listing_id: str) -> PluginListing:
        listing = self._listings.get(listing_id)
        if not listing:
            raise NotFoundException("PluginListing", listing_id)
        return listing

    async def list_plugins(
        self, category: Optional[str] = None, search: str = "",
        sort_by: str = "newest", limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        runtime = get_plugin_runtime()
        listings = list(self._listings.values())

        if category:
            cat_ids = self._categories.get(category, [])
            listings = [l for l in listings if l.listing_id in cat_ids]

        results = []
        for listing in listings:
            try:
                plugin = await runtime.get_plugin(listing.plugin_id)
                if plugin.status == "published":
                    results.append({
                        "listing": listing.to_dict(),
                        "plugin": plugin.to_dict(),
                    })
            except NotFoundException:
                continue

        if search:
            results = [
                r for r in results
                if search.lower() in r["plugin"]["name"].lower()
                or search.lower() in r["plugin"]["description"].lower()
            ]

        if sort_by == "popular":
            results.sort(key=lambda r: r["plugin"]["total_installs"], reverse=True)
        elif sort_by == "price_low":
            results.sort(key=lambda r: r["plugin"]["price"])
        else:
            results.sort(key=lambda r: r["listing"]["created_at"], reverse=True)

        return results[offset:offset + limit]

    async def get_categories(self) -> List[str]:
        return list(self._categories.keys())

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "service": "PluginStore",
            "total_listings": len(self._listings),
            "categories": len(self._categories),
        }


_plugin_store: Optional[PluginStore] = None


def get_plugin_store() -> PluginStore:
    global _plugin_store
    if _plugin_store is None:
        _plugin_store = PluginStore()
    return _plugin_store