"""
Security API endpoints - prompt/tool/output analysis, alerts listing.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any, Optional

from ..core.security_detector import get_security_detector

router = APIRouter(prefix="/security", tags=["security"])


class PromptAnalysisRequest(BaseModel):
    prompt: str
    trace_id: str = ""
    tenant_id: str = "default"
    agent_id: str = ""


class ToolAnalysisRequest(BaseModel):
    tool_name: str
    tool_input: Any = None
    tool_output: Any = None
    permission_granted: bool = True
    trace_id: str = ""
    tenant_id: str = "default"
    agent_id: str = ""


class OutputAnalysisRequest(BaseModel):
    output: str
    trace_id: str = ""
    tenant_id: str = "default"
    agent_id: str = ""


@router.post("/analyze/prompt")
async def analyze_prompt(req: PromptAnalysisRequest):
    return get_security_detector().analyze_prompt(
        req.prompt, req.trace_id, req.tenant_id, req.agent_id,
    )


@router.post("/analyze/tool")
async def analyze_tool(req: ToolAnalysisRequest):
    return get_security_detector().analyze_tool_call(
        req.tool_name, req.tool_input, req.tool_output,
        req.permission_granted, req.trace_id, req.tenant_id, req.agent_id,
    )


@router.post("/analyze/output")
async def analyze_output(req: OutputAnalysisRequest):
    return get_security_detector().analyze_output(
        req.output, req.trace_id, req.tenant_id, req.agent_id,
    )


@router.get("/alerts")
async def list_alerts(tenant_id: str = "", limit: int = 50):
    return {"alerts": get_security_detector().list_alerts(tenant_id, limit)}
