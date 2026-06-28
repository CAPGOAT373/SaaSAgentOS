"""
Agent OS V6.0 - Global Tenant System
Multi-region tenant isolation, sharding, region routing, failover
"""
import uuid
import hashlib
import logging
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from agent_os.config import Region, get_config
from agent_os.core_platform.base import BaseService, ServiceContext
from agent_os.core_platform.exceptions import TenantNotFoundException, ConflictException
from agent_os.core_platform.event_bus import EventTypes

logger = logging.getLogger(__name__)


class TenantTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


class TenantStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"
    TRIAL = "trial"


@dataclass
class Tenant:
    tenant_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    slug: str = ""
    tier: TenantTier = TenantTier.FREE
    status: TenantStatus = TenantStatus.ACTIVE
    primary_region: str = Region.US_EAST.value
    fallback_region: str = ""
    shard_key: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "slug": self.slug,
            "tier": self.tier.value,
            "status": self.status.value,
            "primary_region": self.primary_region,
            "fallback_region": self.fallback_region,
            "shard_key": self.shard_key,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
            "settings": self.settings,
        }


class TenantManager(BaseService):
    """Global tenant management with multi-region support"""

    def __init__(self):
        super().__init__()
        self._tenants: Dict[str, Tenant] = {}
        self._region_tenants: Dict[str, List[str]] = {}  # region -> [tenant_ids]

    @staticmethod
    def generate_shard_key(tenant_id: str, region: str) -> str:
        """Generate shard key for data partitioning"""
        hash_input = f"{tenant_id}:{region}:v6"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    @staticmethod
    def route_to_region(tenant_id: str, preferred_region: Optional[str] = None) -> str:
        """Route tenant to optimal region based on latency/geo"""
        if preferred_region:
            return preferred_region
        # Simple hash-based routing for MVP
        h = int(hashlib.md5(tenant_id.encode()).hexdigest(), 16)
        regions = [r.value for r in Region]
        return regions[h % len(regions)]

    async def create_tenant(
        self, name: str, slug: str, tier: TenantTier = TenantTier.FREE,
        region: Optional[str] = None, ctx: Optional[ServiceContext] = None
    ) -> Tenant:
        # Check slug uniqueness
        for t in self._tenants.values():
            if t.slug == slug:
                raise ConflictException(f"Tenant slug '{slug}' already exists")

        assigned_region = region or self.route_to_region(str(uuid.uuid4()))
        tenant = Tenant(
            tenant_id=str(uuid.uuid4()),
            name=name,
            slug=slug,
            tier=tier,
            primary_region=assigned_region,
            fallback_region=self.route_to_region(str(uuid.uuid4()), None),
            shard_key=self.generate_shard_key(str(uuid.uuid4()), assigned_region),
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

        self._tenants[tenant.tenant_id] = tenant
        if assigned_region not in self._region_tenants:
            self._region_tenants[assigned_region] = []
        self._region_tenants[assigned_region].append(tenant.tenant_id)

        await self.emit_event(EventTypes.TENANT_CREATED, tenant.to_dict(), ctx)
        self.log("info", f"Tenant created: {tenant.tenant_id}", ctx)
        return tenant

    async def get_tenant(self, tenant_id: str) -> Tenant:
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            raise TenantNotFoundException(tenant_id)
        return tenant

    async def get_tenant_by_slug(self, slug: str) -> Tenant:
        for t in self._tenants.values():
            if t.slug == slug:
                return t
        raise TenantNotFoundException(slug)

    async def list_tenants(self, region: Optional[str] = None) -> List[Tenant]:
        if region:
            ids = self._region_tenants.get(region, [])
            return [self._tenants[tid] for tid in ids if tid in self._tenants]
        return list(self._tenants.values())

    async def update_tenant(self, tenant_id: str, updates: Dict[str, Any]) -> Tenant:
        tenant = await self.get_tenant(tenant_id)
        for key, value in updates.items():
            if hasattr(tenant, key):
                setattr(tenant, key, value)
        tenant.updated_at = datetime.now(timezone.utc).isoformat()
        return tenant

    async def delete_tenant(self, tenant_id: str, ctx: Optional[ServiceContext] = None) -> bool:
        tenant = await self.get_tenant(tenant_id)
        tenant.status = TenantStatus.DELETED
        tenant.updated_at = datetime.now(timezone.utc).isoformat()
        await self.emit_event(EventTypes.TENANT_DELETED, {"tenant_id": tenant_id}, ctx)
        return True

    async def region_failover(self, tenant_id: str, from_region: str) -> Tenant:
        """Handle region failover for a tenant"""
        tenant = await self.get_tenant(tenant_id)
        if tenant.fallback_region:
            tenant.primary_region = tenant.fallback_region
            tenant.fallback_region = from_region
            tenant.updated_at = datetime.now(timezone.utc).isoformat()
            await self.emit_event(EventTypes.SYSTEM_REGION_FAILOVER, {
                "tenant_id": tenant_id,
                "from_region": from_region,
                "to_region": tenant.primary_region,
            })
        return tenant

    async def get_region_tenants(self, region: str) -> List[Tenant]:
        ids = self._region_tenants.get(region, [])
        return [self._tenants[tid] for tid in ids if tid in self._tenants]

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "service": "TenantManager",
            "total_tenants": len(self._tenants),
            "regions": len(self._region_tenants),
        }


# Global instance
_tenant_manager: Optional[TenantManager] = None


def get_tenant_manager() -> TenantManager:
    global _tenant_manager
    if _tenant_manager is None:
        _tenant_manager = TenantManager()
    return _tenant_manager