"""
Observability detail endpoints - LLM calls, tool calls, RAG queries, prompt versions, OTel.
"""
from fastapi import APIRouter

from ..core.storage import get_store
from ..core.otel_integration import get_otel
from ..config import config

router = APIRouter(tags=["observability"])


@router.get("/llm-calls")
async def list_llm_calls(tenant_id: str = "", trace_id: str = "", limit: int = 50):
    calls = get_store().list_llm_calls(tenant_id, trace_id, limit)
    return {"calls": [c.to_dict() for c in calls]}


@router.get("/tool-calls")
async def list_tool_calls(tenant_id: str = "", trace_id: str = "", limit: int = 50):
    calls = get_store().list_tool_calls(tenant_id, trace_id, limit)
    return {"calls": [c.to_dict() for c in calls]}


@router.get("/rag-queries")
async def list_rag_queries(tenant_id: str = "", trace_id: str = "", limit: int = 50):
    qs = get_store().list_rag_queries(tenant_id, trace_id, limit)
    return {"queries": [q.to_dict() for q in qs]}


@router.get("/prompt-versions")
async def list_prompt_versions(tenant_id: str = "", agent_id: str = "", limit: int = 50):
    pvs = get_store().list_prompt_versions(tenant_id, agent_id, limit)
    return {"versions": [p.to_dict() for p in pvs]}


@router.get("/errors")
async def list_errors(tenant_id: str = "", trace_id: str = "", limit: int = 50):
    errs = get_store().list_errors(tenant_id, trace_id, limit)
    return {"errors": [e.to_dict() for e in errs]}


@router.get("/otel/traces")
async def otel_traces(tenant_id: str = "", limit: int = 20):
    """Get traces in OpenTelemetry format."""
    return {"traces": get_otel(config.JAEGER_ENDPOINT).list_exportable_traces(tenant_id, limit)}


@router.post("/otel/export/{trace_id}")
async def otel_export(trace_id: str):
    """Export a trace to Jaeger."""
    from ..core.trace_collector import get_collector
    trace = get_collector().get_trace(trace_id)
    if not trace:
        return {"error": "trace not found"}
    return get_otel(config.JAEGER_ENDPOINT).export_to_jaeger(trace)


@router.get("/storage/health")
async def storage_health():
    return get_store().health()
