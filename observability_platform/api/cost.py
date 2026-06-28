"""
Cost API endpoints - tenant/agent/workflow cost, request breakdown, trend.
"""
from fastapi import APIRouter

from ..core.cost_engine import get_cost_engine

router = APIRouter(tags=["cost"])


@router.get("/cost")
async def get_cost(tenant_id: str = ""):
    """GET /cost - Tenant cost summary."""
    return get_cost_engine().get_tenant_cost(tenant_id)


@router.get("/cost/agent")
async def get_agent_cost(tenant_id: str = "", agent_id: str = ""):
    return get_cost_engine().get_agent_cost(tenant_id, agent_id)


@router.get("/cost/workflow")
async def get_workflow_cost(tenant_id: str = "", workflow_id: str = ""):
    return get_cost_engine().get_workflow_cost(tenant_id, workflow_id)


@router.get("/cost/trace/{trace_id}")
async def get_request_cost(trace_id: str):
    """Per-request cost breakdown."""
    return get_cost_engine().get_request_breakdown(trace_id)


@router.get("/cost/trend")
async def get_cost_trend(tenant_id: str = ""):
    return get_cost_engine().get_cost_trend(tenant_id)
