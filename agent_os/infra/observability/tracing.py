"""
Agent OS V6.0 - Distributed Tracing System
Trace/span tracking for execution observability, execution trace graph
"""
import uuid
import time
import logging
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class SpanStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    RUNNING = "running"


@dataclass
class Span:
    span_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    parent_span_id: str = ""
    name: str = ""
    service: str = ""
    status: str = SpanStatus.RUNNING.value
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    tags: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "service": self.service,
            "status": self.status,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "tags": self.tags,
            "events": self.events,
        }


@dataclass
class Trace:
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    root_span_id: str = ""
    name: str = ""
    tenant_id: str = ""
    user_id: str = ""
    spans: List[Span] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    status: str = SpanStatus.RUNNING.value
    total_spans: int = 0
    error_count: int = 0

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "root_span_id": self.root_span_id,
            "name": self.name,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "spans": [s.to_dict() for s in self.spans],
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status,
            "total_spans": self.total_spans,
            "error_count": self.error_count,
            "duration_ms": (self.end_time - self.start_time) * 1000 if self.end_time else 0,
        }

    def build_execution_graph(self) -> Dict[str, Any]:
        """Build execution trace graph for visualization"""
        nodes = []
        edges = []
        for span in self.spans:
            nodes.append({
                "id": span.span_id,
                "label": span.name,
                "service": span.service,
                "duration_ms": span.duration_ms,
                "status": span.status,
                "tags": span.tags,
            })
            if span.parent_span_id:
                edges.append({
                    "from": span.parent_span_id,
                    "to": span.span_id,
                })
        return {
            "trace_id": self.trace_id,
            "name": self.name,
            "nodes": nodes,
            "edges": edges,
            "duration_ms": (self.end_time - self.start_time) * 1000 if self.end_time else 0,
            "total_spans": len(nodes),
            "error_count": self.error_count,
        }


class TraceManager:
    """Distributed tracing for execution observability"""

    def __init__(self, max_traces: int = 1000, max_spans_per_trace: int = 100):
        self._traces: Dict[str, Trace] = {}
        self._active_spans: Dict[str, Span] = {}
        self._max_traces = max_traces
        self._max_spans_per_trace = max_spans_per_trace

    def start_trace(
        self, name: str, tenant_id: str = "", user_id: str = "",
        service: str = "agent-os", metadata: Optional[Dict] = None,
    ) -> Trace:
        """Start a new trace"""
        trace = Trace(
            name=name,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        # Root span
        root_span = self.start_span(
            trace_id=trace.trace_id,
            name=name,
            service=service,
            tags=metadata or {},
        )
        trace.root_span_id = root_span.span_id
        trace.spans.append(root_span)
        self._traces[trace.trace_id] = trace
        self._evict_old_traces()
        return trace

    def start_span(
        self, trace_id: str, name: str, service: str = "",
        parent_span_id: str = "", tags: Optional[Dict] = None,
    ) -> Span:
        """Start a new span within a trace"""
        span = Span(
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            name=name,
            service=service,
            start_time=time.time(),
            tags=tags or {},
        )
        self._active_spans[span.span_id] = span

        trace = self._traces.get(trace_id)
        if trace and len(trace.spans) < self._max_spans_per_trace:
            trace.spans.append(span)
            trace.total_spans = len(trace.spans)

        return span

    def end_span(self, span_id: str, status: str = SpanStatus.OK.value, metadata: Optional[Dict] = None):
        """End a span"""
        span = self._active_spans.pop(span_id, None)
        if span:
            span.end_time = time.time()
            span.duration_ms = (span.end_time - span.start_time) * 1000
            span.status = status
            if metadata:
                span.metadata.update(metadata)

    def add_span_event(self, span_id: str, event_name: str, attributes: Optional[Dict] = None):
        """Add an event to an active span"""
        span = self._active_spans.get(span_id)
        if span:
            span.events.append({
                "name": event_name,
                "timestamp": time.time(),
                "attributes": attributes or {},
            })

    def end_trace(self, trace_id: str, status: str = SpanStatus.OK.value):
        """End a trace"""
        trace = self._traces.get(trace_id)
        if trace:
            trace.end_time = time.time()
            trace.status = status
            trace.error_count = sum(1 for s in trace.spans if s.status == SpanStatus.ERROR.value)

    def get_trace(self, trace_id: str) -> Optional[Trace]:
        return self._traces.get(trace_id)

    def get_execution_graph(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Get execution trace graph for visualization"""
        trace = self._traces.get(trace_id)
        if trace:
            return trace.build_execution_graph()
        return None

    def list_traces(self, tenant_id: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        traces = list(self._traces.values())
        if tenant_id:
            traces = [t for t in traces if t.tenant_id == tenant_id]
        traces.sort(key=lambda t: t.start_time, reverse=True)
        return [t.to_dict() for t in traces[:limit]]

    def get_active_traces(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self._traces.values() if t.status == SpanStatus.RUNNING.value]

    def get_latency_metrics(self, tenant_id: str = "") -> Dict[str, Any]:
        """Get latency metrics across all traces"""
        traces = list(self._traces.values())
        if tenant_id:
            traces = [t for t in traces if t.tenant_id == tenant_id]

        completed = [t for t in traces if t.end_time > 0]
        if not completed:
            return {"avg_latency_ms": 0, "p50_ms": 0, "p95_ms": 0, "p99_ms": 0, "total_traces": 0}

        durations = [(t.end_time - t.start_time) * 1000 for t in completed]
        durations.sort()

        return {
            "avg_latency_ms": sum(durations) / len(durations),
            "p50_ms": durations[len(durations) // 2] if durations else 0,
            "p95_ms": durations[int(len(durations) * 0.95)] if len(durations) > 1 else durations[0] if durations else 0,
            "p99_ms": durations[int(len(durations) * 0.99)] if len(durations) > 1 else durations[0] if durations else 0,
            "min_ms": durations[0] if durations else 0,
            "max_ms": durations[-1] if durations else 0,
            "total_traces": len(completed),
            "error_rate": sum(1 for t in completed if t.error_count > 0) / len(completed) if completed else 0,
        }

    def get_token_usage_stats(self, tenant_id: str = "") -> Dict[str, Any]:
        """Get token usage statistics from traces"""
        total_tokens = 0
        total_cost = 0.0
        traces = list(self._traces.values())
        if tenant_id:
            traces = [t for t in traces if t.tenant_id == tenant_id]

        for trace in traces:
            for span in trace.spans:
                if "tokens" in span.tags:
                    total_tokens += span.tags.get("tokens", 0)
                if "cost" in span.tags:
                    total_cost += span.tags.get("cost", 0.0)

        return {
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "total_traces": len(traces),
        }

    def _evict_old_traces(self):
        """Remove oldest traces when exceeding max_traces"""
        if len(self._traces) > self._max_traces:
            sorted_traces = sorted(
                self._traces.items(),
                key=lambda x: x[1].start_time,
            )
            to_remove = len(self._traces) - self._max_traces
            for trace_id, _ in sorted_traces[:to_remove]:
                del self._traces[trace_id]

    def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "service": "TraceManager",
            "total_traces": len(self._traces),
            "active_spans": len(self._active_spans),
            "active_traces": len(self.get_active_traces()),
        }


_trace_manager: Optional[TraceManager] = None


def get_trace_manager() -> TraceManager:
    global _trace_manager
    if _trace_manager is None:
        _trace_manager = TraceManager()
    return _trace_manager