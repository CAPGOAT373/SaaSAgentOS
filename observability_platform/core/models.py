"""
AI Agent Observability Platform - Core Data Models
Defines all entities: Trace, Span, Event, Log, Metric, LLMCall, ToolCall, RAGQuery, etc.
"""
import uuid
import time
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> float:
    return time.time()


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:16]}"


class SpanType(str, Enum):
    LLM = "llm"
    TOOL = "tool"
    RAG = "rag"
    PROMPT = "prompt"
    AGENT = "agent"
    WORKFLOW = "workflow"


class SpanStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    RUNNING = "running"


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class EventType(str, Enum):
    AGENT_START = "agent_start"
    PROMPT_BUILD = "prompt_build"
    RAG_SEARCH = "rag_search"
    TOOL_CALL = "tool_call"
    LLM_CALL = "llm_call"
    OUTPUT = "output"
    ERROR = "error"
    COST = "cost"


class AlertLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Span:
    span_id: str = field(default_factory=lambda: _uid("span_"))
    trace_id: str = ""
    parent_span_id: str = ""
    name: str = ""
    type: str = SpanType.AGENT.value
    service: str = ""
    status: str = SpanStatus.RUNNING.value
    start_time: float = field(default_factory=_now)
    end_time: float = 0.0
    duration_ms: float = 0.0
    tags: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    input: Any = None
    output: Any = None

    def to_dict(self) -> dict:
        return {
            "span_id": self.span_id, "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id, "name": self.name,
            "type": self.type, "service": self.service, "status": self.status,
            "start_time": self.start_time, "end_time": self.end_time,
            "duration_ms": self.duration_ms, "tags": self.tags,
            "events": self.events, "metadata": self.metadata,
            "input": self.input, "output": self.output,
        }


@dataclass
class Trace:
    trace_id: str = field(default_factory=lambda: _uid("trace_"))
    name: str = ""
    tenant_id: str = ""
    agent_id: str = ""
    user_id: str = ""
    root_span_id: str = ""
    spans: List[Span] = field(default_factory=list)
    start_time: float = field(default_factory=_now)
    end_time: float = 0.0
    status: str = SpanStatus.RUNNING.value
    error_count: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    risk_score: float = 0.0
    alert_level: str = AlertLevel.NONE.value
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000 if self.end_time else 0.0

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id, "name": self.name, "tenant_id": self.tenant_id,
            "agent_id": self.agent_id, "user_id": self.user_id,
            "root_span_id": self.root_span_id,
            "spans": [s.to_dict() for s in self.spans],
            "start_time": self.start_time, "end_time": self.end_time,
            "duration_ms": self.duration_ms, "status": self.status,
            "error_count": self.error_count, "total_tokens": self.total_tokens,
            "total_cost": self.total_cost, "risk_score": self.risk_score,
            "alert_level": self.alert_level, "metadata": self.metadata,
        }

    def build_execution_graph(self) -> Dict[str, Any]:
        nodes, edges = [], []
        for span in self.spans:
            nodes.append({
                "id": span.span_id, "label": span.name, "type": span.type,
                "service": span.service, "duration_ms": span.duration_ms,
                "status": span.status, "tags": span.tags,
            })
            if span.parent_span_id:
                edges.append({"from": span.parent_span_id, "to": span.span_id})
        return {
            "trace_id": self.trace_id, "name": self.name, "nodes": nodes,
            "edges": edges, "duration_ms": self.duration_ms,
            "total_spans": len(nodes), "error_count": self.error_count,
            "status": self.status,
        }

    def build_timeline(self) -> List[Dict[str, Any]]:
        if not self.spans:
            return []
        base = min(s.start_time for s in self.spans)
        timeline = []
        for span in sorted(self.spans, key=lambda s: s.start_time):
            timeline.append({
                "span_id": span.span_id, "name": span.name, "type": span.type,
                "status": span.status,
                "start_offset_ms": (span.start_time - base) * 1000,
                "duration_ms": span.duration_ms or (span.end_time - span.start_time) * 1000,
                "depth": self._span_depth(span.span_id),
                "parent_span_id": span.parent_span_id,
            })
        return timeline

    def _span_depth(self, span_id: str) -> int:
        depth = 0
        by_id = {s.span_id: s for s in self.spans}
        cur = by_id.get(span_id)
        while cur and cur.parent_span_id:
            depth += 1
            cur = by_id.get(cur.parent_span_id)
            if depth > 50:
                break
        return depth


@dataclass
class LogEntry:
    log_id: str = field(default_factory=lambda: _uid("log_"))
    trace_id: str = ""
    span_id: str = ""
    tenant_id: str = ""
    level: str = LogLevel.INFO.value
    message: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "log_id": self.log_id, "trace_id": self.trace_id,
            "span_id": self.span_id, "tenant_id": self.tenant_id,
            "level": self.level, "message": self.message,
            "payload": self.payload, "timestamp": self.timestamp,
            "timestamp_iso": datetime.fromtimestamp(self.timestamp, timezone.utc).isoformat(),
        }


@dataclass
class LLMCall:
    call_id: str = field(default_factory=lambda: _uid("llm_"))
    trace_id: str = ""
    span_id: str = ""
    tenant_id: str = ""
    agent_id: str = ""
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    cost: float = 0.0
    quality_score: float = 0.0
    prompt: str = ""
    response: str = ""
    status: str = SpanStatus.OK.value
    timestamp: float = field(default_factory=_now)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class ToolCall:
    call_id: str = field(default_factory=lambda: _uid("tool_"))
    trace_id: str = ""
    span_id: str = ""
    tenant_id: str = ""
    agent_id: str = ""
    tool_name: str = ""
    input: Any = None
    output: Any = None
    latency_ms: float = 0.0
    error: str = ""
    permission_granted: bool = True
    status: str = SpanStatus.OK.value
    timestamp: float = field(default_factory=_now)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class RAGQuery:
    query_id: str = field(default_factory=lambda: _uid("rag_"))
    trace_id: str = ""
    span_id: str = ""
    tenant_id: str = ""
    agent_id: str = ""
    query: str = ""
    embedding_dim: int = 0
    vector_search_results: int = 0
    rerank_scores: List[float] = field(default_factory=list)
    retrieved_docs: List[Dict[str, Any]] = field(default_factory=list)
    latency_ms: float = 0.0
    status: str = SpanStatus.OK.value
    timestamp: float = field(default_factory=_now)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class PromptVersion:
    version_id: str = field(default_factory=lambda: _uid("pv_"))
    tenant_id: str = ""
    agent_id: str = ""
    prompt_name: str = ""
    version: str = "1.0.0"
    template: str = ""
    variables: Dict[str, Any] = field(default_factory=dict)
    rendered: str = ""
    output: str = ""
    timestamp: float = field(default_factory=_now)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class CostRecord:
    record_id: str = field(default_factory=lambda: _uid("cost_"))
    trace_id: str = ""
    tenant_id: str = ""
    agent_id: str = ""
    workflow_id: str = ""
    component: str = ""  # llm | tool | rag
    tokens: int = 0
    cost: float = 0.0
    currency: str = "USD"
    timestamp: float = field(default_factory=_now)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class ErrorRecord:
    error_id: str = field(default_factory=lambda: _uid("err_"))
    trace_id: str = ""
    span_id: str = ""
    tenant_id: str = ""
    agent_id: str = ""
    error_type: str = ""
    message: str = ""
    stack: str = ""
    timestamp: float = field(default_factory=_now)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class SecurityAlert:
    alert_id: str = field(default_factory=lambda: _uid("sec_"))
    trace_id: str = ""
    tenant_id: str = ""
    agent_id: str = ""
    risk_type: str = ""  # prompt_injection | tool_misuse | data_leakage | unauthorized_access
    risk_score: float = 0.0
    alert_level: str = AlertLevel.LOW.value
    auto_block: bool = False
    detail: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=_now)

    def to_dict(self) -> dict:
        return self.__dict__.copy()
