"""
Trace Collector - Collects all Agent events, generates trace_id, correlates spans.
The central hub of the observability platform.
"""
import time
import logging
from typing import Optional, Dict, Any, List

from .models import (
    Trace, Span, SpanType, SpanStatus, EventType, AlertLevel,
    LogEntry, LogLevel,
)
from .storage import get_store

logger = logging.getLogger(__name__)


class TraceCollector:
    """Collects traces and spans, correlates them, and persists to storage."""

    def __init__(self):
        self._store = get_store()
        self._active_spans: Dict[str, Span] = {}

    def start_trace(
        self, name: str, tenant_id: str = "default", agent_id: str = "",
        user_id: str = "", metadata: Optional[Dict] = None,
    ) -> Trace:
        trace = Trace(
            name=name, tenant_id=tenant_id, agent_id=agent_id,
            user_id=user_id, metadata=metadata or {},
        )
        root = self.start_span(
            trace_id=trace.trace_id, name=name,
            span_type=SpanType.AGENT.value, service="agent",
            tags=metadata or {},
        )
        trace.root_span_id = root.span_id
        trace.spans.append(root)
        self._store.save_trace(trace)
        self._log(trace, LogLevel.INFO, f"Trace started: {name}")
        return trace

    def start_span(
        self, trace_id: str, name: str, span_type: str = SpanType.AGENT.value,
        service: str = "", parent_span_id: str = "",
        tags: Optional[Dict] = None, input_data: Any = None,
    ) -> Span:
        span = Span(
            trace_id=trace_id, parent_span_id=parent_span_id, name=name,
            type=span_type, service=service, start_time=time.time(),
            tags=tags or {}, input=input_data,
        )
        self._active_spans[span.span_id] = span
        trace = self._store.get_trace(trace_id)
        if trace:
            trace.spans.append(span)
            self._store.save_trace(trace)
        return span

    def end_span(
        self, span_id: str, status: str = SpanStatus.OK.value,
        output: Any = None, metadata: Optional[Dict] = None,
    ) -> Optional[Span]:
        span = self._active_spans.pop(span_id, None)
        if not span:
            return None
        span.end_time = time.time()
        span.duration_ms = (span.end_time - span.start_time) * 1000
        span.status = status
        span.output = output
        if metadata:
            span.metadata.update(metadata)
        # update trace
        trace = self._store.get_trace(span.trace_id)
        if trace:
            self._store.save_trace(trace)
        return span

    def add_span_event(self, span_id: str, event_name: str, attributes: Optional[Dict] = None):
        span = self._active_spans.get(span_id)
        if span:
            span.events.append({
                "name": event_name, "timestamp": time.time(),
                "attributes": attributes or {},
            })

    def end_trace(self, trace_id: str, status: str = SpanStatus.OK.value) -> Optional[Trace]:
        trace = self._store.get_trace(trace_id)
        if not trace:
            return None
        trace.end_time = time.time()
        trace.status = status
        trace.error_count = sum(1 for s in trace.spans if s.status == SpanStatus.ERROR.value)
        # close any dangling spans
        for span in trace.spans:
            if span.status == SpanStatus.RUNNING.value:
                span.end_time = span.end_time or time.time()
                span.duration_ms = (span.end_time - span.start_time) * 1000
                span.status = status
        self._store.save_trace(trace)
        self._log(trace, LogLevel.INFO if status == SpanStatus.OK.value else LogLevel.ERROR,
                  f"Trace ended: {trace.name} (status={status})")
        return trace

    def update_trace(
        self, trace_id: str, total_tokens: Optional[int] = None,
        total_cost: Optional[float] = None, risk_score: Optional[float] = None,
        alert_level: Optional[str] = None,
    ) -> Optional[Trace]:
        trace = self._store.get_trace(trace_id)
        if not trace:
            return None
        if total_tokens is not None:
            trace.total_tokens = total_tokens
        if total_cost is not None:
            trace.total_cost = total_cost
        if risk_score is not None:
            trace.risk_score = risk_score
        if alert_level is not None:
            trace.alert_level = alert_level
        self._store.save_trace(trace)
        return trace

    def get_trace(self, trace_id: str) -> Optional[Trace]:
        return self._store.get_trace(trace_id)

    def get_timeline(self, trace_id: str) -> List[Dict[str, Any]]:
        trace = self._store.get_trace(trace_id)
        return trace.build_timeline() if trace else []

    def get_execution_graph(self, trace_id: str) -> Optional[Dict[str, Any]]:
        trace = self._store.get_trace(trace_id)
        return trace.build_execution_graph() if trace else None

    def list_traces(
        self, tenant_id: str = "", agent_id: str = "",
        limit: int = 50, offset: int = 0, status: str = "",
    ) -> Dict[str, Any]:
        traces, total = self._store.list_traces(tenant_id, agent_id, limit, offset, status)
        return {
            "traces": [t.to_dict() for t in traces],
            "total": total, "limit": limit, "offset": offset,
        }

    def _log(self, trace: Trace, level: LogLevel, message: str, payload: Optional[Dict] = None):
        self._store.add_log(LogEntry(
            trace_id=trace.trace_id, tenant_id=trace.tenant_id,
            level=level.value, message=message, payload=payload or {},
        ))


_collector: Optional[TraceCollector] = None


def get_collector() -> TraceCollector:
    global _collector
    if _collector is None:
        _collector = TraceCollector()
    return _collector
