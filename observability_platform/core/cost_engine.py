"""
Cost Engine - Tracks costs across tenant/agent/workflow/request dimensions.
Provides per-request cost breakdown and aggregation.
"""
import logging
from typing import Optional, Dict, Any, List
from collections import defaultdict

from .storage import get_store

logger = logging.getLogger(__name__)


class CostEngine:
    """Cost tracking and analysis engine."""

    def __init__(self):
        self._store = get_store()
        # pricing per 1K tokens (USD)
        self._pricing = {
            "gpt-4": {"prompt": 0.03, "completion": 0.06},
            "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
            "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
            "claude-3-opus": {"prompt": 0.015, "completion": 0.075},
            "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
            "default": {"prompt": 0.002, "completion": 0.006},
        }

    def compute_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        rates = self._pricing.get(model, self._pricing["default"])
        return (prompt_tokens / 1000.0) * rates["prompt"] + (completion_tokens / 1000.0) * rates["completion"]

    def get_tenant_cost(self, tenant_id: str = "") -> Dict[str, Any]:
        records = self._store.list_cost_records(tenant_id, limit=100000)
        total_cost = sum(r.cost for r in records)
        total_tokens = sum(r.tokens for r in records)
        by_component: Dict[str, Dict[str, float]] = defaultdict(lambda: {"cost": 0.0, "tokens": 0, "count": 0})
        by_agent: Dict[str, float] = defaultdict(float)
        for r in records:
            by_component[r.component]["cost"] += r.cost
            by_component[r.component]["tokens"] += r.tokens
            by_component[r.component]["count"] += 1
            if r.agent_id:
                by_agent[r.agent_id] += r.cost
        return {
            "tenant_id": tenant_id or "all",
            "total_cost_usd": round(total_cost, 6),
            "total_tokens": total_tokens,
            "total_records": len(records),
            "by_component": {k: dict(v) for k, v in by_component.items()},
            "by_agent": dict(by_agent),
        }

    def get_agent_cost(self, tenant_id: str = "", agent_id: str = "") -> Dict[str, Any]:
        records = self._store.list_cost_records(tenant_id, limit=100000)
        if agent_id:
            records = [r for r in records if r.agent_id == agent_id]
        return {
            "agent_id": agent_id or "all",
            "total_cost_usd": round(sum(r.cost for r in records), 6),
            "total_tokens": sum(r.tokens for r in records),
            "records": len(records),
        }

    def get_workflow_cost(self, tenant_id: str = "", workflow_id: str = "") -> Dict[str, Any]:
        records = self._store.list_cost_records(tenant_id, limit=100000)
        if workflow_id:
            records = [r for r in records if r.workflow_id == workflow_id]
        return {
            "workflow_id": workflow_id or "all",
            "total_cost_usd": round(sum(r.cost for r in records), 6),
            "total_tokens": sum(r.tokens for r in records),
            "records": len(records),
        }

    def get_request_breakdown(self, trace_id: str) -> Dict[str, Any]:
        """Per-request cost breakdown for a single trace."""
        records = self._store.list_cost_records(limit=100000)
        records = [r for r in records if r.trace_id == trace_id]
        breakdown = []
        for r in records:
            breakdown.append({
                "component": r.component, "tokens": r.tokens,
                "cost_usd": round(r.cost, 6), "timestamp": r.timestamp,
            })
        return {
            "trace_id": trace_id,
            "total_cost_usd": round(sum(r.cost for r in records), 6),
            "total_tokens": sum(r.tokens for r in records),
            "breakdown": breakdown,
        }

    def get_cost_trend(self, tenant_id: str = "") -> Dict[str, Any]:
        """Cost over time (bucketed by hour)."""
        records = self._store.list_cost_records(tenant_id, limit=100000)
        buckets: Dict[str, float] = defaultdict(float)
        for r in records:
            import time as _t
            from datetime import datetime, timezone
            dt = datetime.fromtimestamp(r.timestamp, timezone.utc)
            bucket = dt.strftime("%Y-%m-%dT%H:00:00Z")
            buckets[bucket] += r.cost
        return {
            "trend": [{"timestamp": k, "cost_usd": round(v, 6)} for k, v in sorted(buckets.items())],
        }


_cost_engine: Optional[CostEngine] = None


def get_cost_engine() -> CostEngine:
    global _cost_engine
    if _cost_engine is None:
        _cost_engine = CostEngine()
    return _cost_engine
