"""
Trace API endpoints - trace start/span/event, retrieval, timeline, DAG.
"""
from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from ..core.trace_collector import get_collector
from ..core.event_pipeline import get_pipeline, BaseEvent
from ..core.models import SpanType, EventType, SpanStatus

router = APIRouter(prefix="/trace", tags=["traces"])


class TraceStartRequest(BaseModel):
    name: str
    tenant_id: str = "default"
    agent_id: str = ""
    user_id: str = ""
    metadata: Dict[str, Any] = {}


class SpanRequest(BaseModel):
    trace_id: str
    name: str
    type: str = SpanType.AGENT.value
    service: str = ""
    parent_span_id: str = ""
    tags: Dict[str, Any] = {}
    input: Any = None


class SpanEndRequest(BaseModel):
    span_id: str
    status: str = SpanStatus.OK.value
    output: Any = None
    metadata: Dict[str, Any] = {}


class EventRequest(BaseModel):
    trace_id: str = ""
    span_id: str = ""
    tenant_id: str = "default"
    agent_id: str = ""
    event_type: str
    payload: Dict[str, Any] = {}


class TraceEndRequest(BaseModel):
    status: str = SpanStatus.OK.value


@router.post("/start")
async def start_trace(req: TraceStartRequest):
    """POST /trace/start - Start a new trace."""
    trace = get_collector().start_trace(
        name=req.name, tenant_id=req.tenant_id, agent_id=req.agent_id,
        user_id=req.user_id, metadata=req.metadata,
    )
    # emit agent_start event
    get_pipeline().emit(BaseEvent(
        trace_id=trace.trace_id, tenant_id=req.tenant_id, agent_id=req.agent_id,
        event_type=EventType.AGENT_START.value,
        payload={"name": req.name, "root_span_id": trace.root_span_id},
    ))
    return trace.to_dict()


@router.post("/span")
async def start_span(req: SpanRequest):
    """POST /trace/span - Start a new span within a trace."""
    span = get_collector().start_span(
        trace_id=req.trace_id, name=req.name, span_type=req.type,
        service=req.service, parent_span_id=req.parent_span_id,
        tags=req.tags, input_data=req.input,
    )
    return span.to_dict()


@router.post("/span/end")
async def end_span(req: SpanEndRequest):
    """POST /trace/span/end - End a span."""
    span = get_collector().end_span(
        req.span_id, status=req.status, output=req.output, metadata=req.metadata,
    )
    return span.to_dict() if span else {"error": "span not found"}


@router.post("/event")
async def emit_event(req: EventRequest):
    """POST /trace/event - Emit an observability event."""
    event = BaseEvent(
        trace_id=req.trace_id, span_id=req.span_id, tenant_id=req.tenant_id,
        agent_id=req.agent_id, event_type=req.event_type, payload=req.payload,
    )
    result = get_pipeline().emit(event)
    return result


@router.post("/{trace_id}/end")
async def end_trace(trace_id: str, req: TraceEndRequest):
    """End a trace."""
    trace = get_collector().end_trace(trace_id, status=req.status)
    return trace.to_dict() if trace else {"error": "trace not found"}


@router.get("")
@router.get("/")
async def list_traces(
    tenant_id: str = "", agent_id: str = "",
    limit: int = 50, offset: int = 0, status: str = "",
):
    """GET /trace - List traces."""
    return get_collector().list_traces(tenant_id, agent_id, limit, offset, status)


@router.get("/{trace_id}")
async def get_trace(trace_id: str):
    """GET /trace/{id} - Get full trace detail."""
    trace = get_collector().get_trace(trace_id)
    return trace.to_dict() if trace else {"error": "trace not found"}


@router.get("/{trace_id}/timeline")
async def get_timeline(trace_id: str):
    """GET /trace/{id}/timeline - Get trace timeline view."""
    timeline = get_collector().get_timeline(trace_id)
    return {"trace_id": trace_id, "timeline": timeline}


@router.get("/{trace_id}/graph")
async def get_graph(trace_id: str):
    """GET /trace/{id}/graph - Get execution DAG graph."""
    graph = get_collector().get_execution_graph(trace_id)
    return graph or {"error": "trace not found"}


@router.get("/{trace_id}/steps")
async def get_steps(trace_id: str):
    """GET /trace/{id}/steps - Step-by-step execution for debugging."""
    from ..core.replay_engine import get_replay_engine
    return get_replay_engine().step_by_step(trace_id)
