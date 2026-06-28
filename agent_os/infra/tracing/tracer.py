"""
Agent OS V6.0 - Distributed Tracing (OpenTelemetry stub)
"""
import uuid
import time
from contextlib import contextmanager
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from agent_os.config import get_config


@dataclass
class SpanContext:
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    span_id: str = field(default_factory=lambda: str(uuid.uuid4())[:16])
    parent_span_id: str = ""


@dataclass
class Span:
    name: str = ""
    context: SpanContext = field(default_factory=SpanContext)
    kind: str = "internal"
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    status: str = "ok"
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)

    def add_event(self, name: str, attributes: Optional[Dict] = None):
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {},
        })

    def set_attribute(self, key: str, value: Any):
        self.attributes[key] = value

    def finish(self):
        self.end_time = time.time()

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return (time.time() - self.start_time) * 1000

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "trace_id": self.context.trace_id,
            "span_id": self.context.span_id,
            "parent_span_id": self.context.parent_span_id,
            "kind": self.kind,
            "start_time": self.start_time,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
        }


class Tracer:
    """Distributed tracer (OpenTelemetry compatible stub)"""

    def __init__(self):
        self._spans: List[Span] = []
        self._active_spans: List[Span] = []
        self._config = get_config().observability

    def start_span(
        self, name: str, parent_span: Optional[Span] = None,
        kind: str = "internal", attributes: Optional[Dict] = None
    ) -> Span:
        parent_ctx = parent_span.context if parent_span else SpanContext()
        span = Span(
            name=name,
            context=SpanContext(
                trace_id=parent_ctx.trace_id,
                parent_span_id=parent_ctx.span_id,
            ),
            kind=kind,
        )
        if attributes:
            span.attributes = attributes
        self._active_spans.append(span)
        return span

    def end_span(self, span: Span):
        span.finish()
        self._active_spans = [s for s in self._active_spans if s.context.span_id != span.context.span_id]
        self._spans.append(span)

    @contextmanager
    def start_as_current_span(self, name: str, **kwargs):
        span = self.start_span(name, **kwargs)
        try:
            yield span
        finally:
            self.end_span(span)

    def get_spans(self, trace_id: Optional[str] = None) -> List[Span]:
        if trace_id:
            return [s for s in self._spans if s.context.trace_id == trace_id]
        return self._spans

    def get_trace(self, trace_id: str) -> Dict[str, Any]:
        spans = self.get_spans(trace_id)
        return {
            "trace_id": trace_id,
            "spans": [s.to_dict() for s in spans],
            "total_spans": len(spans),
        }

    def get_all_traces(self) -> List[Dict[str, Any]]:
        trace_ids = set(s.context.trace_id for s in self._spans)
        return [self.get_trace(tid) for tid in trace_ids]


_tracer: Optional[Tracer] = None


def get_tracer() -> Tracer:
    global _tracer
    if _tracer is None:
        _tracer = Tracer()
    return _tracer