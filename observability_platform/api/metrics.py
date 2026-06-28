"""
Metrics API endpoints - token, latency, error, tool, tenant usage, heatmap.
"""
from fastapi import APIRouter

from ..core.metrics_engine import get_metrics_engine
from ..core.log_system import get_log_system

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def get_metrics(tenant_id: str = ""):
    """GET /metrics - Overview metrics dashboard."""
    return get_metrics_engine().get_overview(tenant_id)


@router.get("/metrics/tokens")
async def get_token_metrics(tenant_id: str = ""):
    return get_metrics_engine().get_token_stats(tenant_id)


@router.get("/metrics/latency")
async def get_latency_metrics(tenant_id: str = ""):
    return get_metrics_engine().get_latency_stats(tenant_id)


@router.get("/metrics/errors")
async def get_error_metrics(tenant_id: str = ""):
    return get_metrics_engine().get_error_stats(tenant_id)


@router.get("/metrics/tools")
async def get_tool_metrics(tenant_id: str = ""):
    return get_metrics_engine().get_tool_stats(tenant_id)


@router.get("/metrics/tenant")
async def get_tenant_usage(tenant_id: str = ""):
    return get_metrics_engine().get_tenant_usage(tenant_id)


@router.get("/metrics/heatmap")
async def get_heatmap(tenant_id: str = ""):
    return get_metrics_engine().get_latency_heatmap(tenant_id)


@router.get("/logs")
async def get_logs(trace_id: str = "", tenant_id: str = "", level: str = "", limit: int = 100):
    """GET /logs - Structured logs."""
    return {"logs": get_log_system().list_logs(trace_id, tenant_id, level, limit)}


@router.get("/logs/prompt")
async def get_prompt_logs(tenant_id: str = "", limit: int = 50):
    return {"logs": get_log_system().get_prompt_logs(tenant_id, limit)}


@router.get("/logs/tool")
async def get_tool_logs(tenant_id: str = "", limit: int = 50):
    return {"logs": get_log_system().get_tool_logs(tenant_id, limit)}


@router.get("/logs/rag")
async def get_rag_logs(tenant_id: str = "", limit: int = 50):
    return {"logs": get_log_system().get_rag_logs(tenant_id, limit)}


@router.get("/logs/llm")
async def get_llm_logs(tenant_id: str = "", limit: int = 50):
    return {"logs": get_log_system().get_llm_logs(tenant_id, limit)}
