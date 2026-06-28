"""
Agent OS V6.0 - Usage Service
Usage tracking, analytics, metering, quota management
"""
import uuid
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from agent_os.core_platform.base import BaseService, ServiceContext
from agent_os.core_platform.billing_engine import get_billing_engine


@dataclass
class UsageRecord:
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    user_id: str = ""
    resource_type: str = ""
    resource_id: str = ""
    action: str = ""
    quantity: int = 1
    cost: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    region: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id, "tenant_id": self.tenant_id,
            "user_id": self.user_id, "resource_type": self.resource_type,
            "resource_id": self.resource_id, "action": self.action,
            "quantity": self.quantity, "cost": self.cost,
            "timestamp": self.timestamp, "region": self.region,
        }


@dataclass
class UsageSummary:
    tenant_id: str = ""
    period: str = "daily"
    total_calls: int = 0
    total_cost: float = 0.0
    agent_executions: int = 0
    plugin_executions: int = 0
    workflow_executions: int = 0
    api_calls: int = 0
    start_date: str = ""
    end_date: str = ""

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id, "period": self.period,
            "total_calls": self.total_calls, "total_cost": self.total_cost,
            "agent_executions": self.agent_executions,
            "plugin_executions": self.plugin_executions,
            "workflow_executions": self.workflow_executions,
            "api_calls": self.api_calls,
            "start_date": self.start_date, "end_date": self.end_date,
        }


class UsageService(BaseService):
    """Usage Service: tracking, analytics, metering"""

    def __init__(self):
        super().__init__()
        self._records: List[UsageRecord] = []
        self._quotas: Dict[str, Dict[str, int]] = {}  # tenant_id -> {resource: max_quota}

    async def track_usage(
        self, tenant_id: str, resource_type: str, resource_id: str,
        action: str, quantity: int = 1, cost: float = 0.0,
        user_id: str = "", region: str = "",
        metadata: Optional[Dict] = None, ctx: Optional[ServiceContext] = None
    ) -> UsageRecord:
        record = UsageRecord(
            tenant_id=tenant_id, user_id=user_id, resource_type=resource_type,
            resource_id=resource_id, action=action, quantity=quantity,
            cost=cost, region=region, metadata=metadata or {},
        )
        self._records.append(record)

        if cost > 0:
            billing = get_billing_engine()
            await billing.record_usage(
                tenant_id=tenant_id, resource_type=resource_type,
                resource_id=resource_id, amount=cost, metadata=metadata, ctx=ctx,
            )

        return record

    async def get_usage(
        self, tenant_id: str, resource_type: str = "",
        limit: int = 100, offset: int = 0
    ) -> List[UsageRecord]:
        records = [r for r in self._records if r.tenant_id == tenant_id]
        if resource_type:
            records = [r for r in records if r.resource_type == resource_type]
        return sorted(records, key=lambda r: r.timestamp, reverse=True)[offset:offset + limit]

    async def get_usage_summary(self, tenant_id: str) -> UsageSummary:
        records = [r for r in self._records if r.tenant_id == tenant_id]
        summary = UsageSummary(tenant_id=tenant_id)
        for r in records:
            summary.total_calls += r.quantity
            summary.total_cost += r.cost
            if r.resource_type == "agent":
                summary.agent_executions += r.quantity
            elif r.resource_type == "plugin":
                summary.plugin_executions += r.quantity
            elif r.resource_type == "workflow":
                summary.workflow_executions += r.quantity
            elif r.resource_type == "api":
                summary.api_calls += r.quantity
        return summary

    async def set_quota(self, tenant_id: str, resource_type: str, max_quota: int):
        if tenant_id not in self._quotas:
            self._quotas[tenant_id] = {}
        self._quotas[tenant_id][resource_type] = max_quota

    async def check_quota(self, tenant_id: str, resource_type: str) -> Dict[str, Any]:
        quota = self._quotas.get(tenant_id, {}).get(resource_type, -1)
        records = [r for r in self._records if r.tenant_id == tenant_id and r.resource_type == resource_type]
        current_usage = sum(r.quantity for r in records)
        return {
            "tenant_id": tenant_id,
            "resource_type": resource_type,
            "max_quota": quota if quota > 0 else "unlimited",
            "current_usage": current_usage,
            "remaining": quota - current_usage if quota > 0 else "unlimited",
        }

    async def get_tenant_analytics(self, tenant_id: str) -> Dict[str, Any]:
        records = [r for r in self._records if r.tenant_id == tenant_id]
        summary = await self.get_usage_summary(tenant_id)

        resource_breakdown = {}
        for r in records:
            resource_breakdown[r.resource_type] = resource_breakdown.get(r.resource_type, 0) + r.quantity

        return {
            "tenant_id": tenant_id,
            "summary": summary.to_dict(),
            "resource_breakdown": resource_breakdown,
            "total_records": len(records),
        }

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "service": "UsageService",
            "total_records": len(self._records),
        }


_usage_service: Optional[UsageService] = None


def get_usage_service() -> UsageService:
    global _usage_service
    if _usage_service is None:
        _usage_service = UsageService()
    return _usage_service