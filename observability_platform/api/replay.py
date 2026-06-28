"""
Replay API endpoints - exact and debug replay modes.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from ..core.replay_engine import get_replay_engine

router = APIRouter(prefix="/trace/replay", tags=["replay"])


class ReplayRequest(BaseModel):
    trace_id: str
    tenant_id: str = ""
    mode: str = "exact"  # exact | debug
    new_prompt: Optional[str] = ""
    new_model: Optional[str] = ""


@router.post("")
async def replay_trace(req: ReplayRequest):
    """POST /trace/replay - Replay a trace (exact or debug mode)."""
    engine = get_replay_engine()
    if req.mode == "debug":
        return engine.debug_replay(
            req.trace_id, tenant_id=req.tenant_id,
            new_prompt=req.new_prompt or "", new_model=req.new_model or "",
        )
    return engine.exact_replay(req.trace_id, tenant_id=req.tenant_id)


@router.post("/exact")
async def exact_replay(trace_id: str, tenant_id: str = ""):
    return get_replay_engine().exact_replay(trace_id, tenant_id)


@router.post("/debug")
async def debug_replay(req: ReplayRequest):
    return get_replay_engine().debug_replay(
        req.trace_id, tenant_id=req.tenant_id,
        new_prompt=req.new_prompt or "", new_model=req.new_model or "",
    )
