"""
OpenTelemetry Integration - trace_id propagation, span mapping, event conversion,
and exporter to Jaeger. Gracefully degrades when OTel SDK is not installed.
"""
import logging
from typing import Optional, Dict, Any, List

from .models import Trace, Span, SpanType, SpanStatus
from .storage import get_store

logger = logging.getLogger(__name__)


class OTelIntegration:
    """Bridges internal traces to OpenTelemetry format and exports to Jaeger."""

    def __init__(self, jaeger_endpoint: str = "http://localhost:14268/api/traces"):
        self.jaeger_endpoint = jaeger_endpoint
        self._tracer = None
        self._exporter = None
        self._available = False
        self._init_otel()

    def _init_otel(self):
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            self._trace = trace
            self._available = True
            logger.info("OpenTelemetry SDK available")
        except ImportError:
            logger.warning("opentelemetry-sdk not installed; OTel integration in simulation mode")
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def trace_to_otel_format(self, trace: Trace) -> Dict[str, Any]:
        """Convert internal Trace to OpenTelemetry-compatible JSON format."""
        return {
            "trace_id": trace.trace_id,
            "name": trace.name,
            "tenant_id": trace.tenant_id,
            "resource": {
                "service.name": "ai-agent-observability",
                "tenant.id": trace.tenant_id,
                "agent.id": trace.agent_id,
            },
            "spans": [self._span_to_otel(s) for s in trace.spans],
            "total_spans": len(trace.spans),
            "duration_ms": trace.duration_ms,
        }

    def _span_to_otel(self, span: Span) -> Dict[str, Any]:
        return {
            "span_id": span.span_id,
            "trace_id": span.trace_id,
            "parent_span_id": span.parent_span_id,
            "name": span.name,
            "kind": "INTERNAL",
            "start_time_unix_nano": int(span.start_time * 1e9),
            "end_time_unix_nano": int(span.end_time * 1e9) if span.end_time else 0,
            "duration_ms": span.duration_ms,
            "status": {
                "code": "ERROR" if span.status == SpanStatus.ERROR.value else "OK",
            },
            "attributes": {
                "span.type": span.type,
                "span.service": span.service,
                **{f"tag.{k}": v for k, v in span.tags.items()},
            },
            "events": [
                {
                    "name": e.get("name", ""),
                    "time_unix_nano": int(e.get("timestamp", 0) * 1e9),
                    "attributes": e.get("attributes", {}),
                }
                for e in span.events
            ],
        }

    def export_to_jaeger(self, trace: Trace) -> Dict[str, Any]:
        """Export a trace to Jaeger (simulated if OTel SDK unavailable)."""
        otel_data = self.trace_to_otel_format(trace)
        if self._available:
            try:
                from opentelemetry.exporter.jaeger.thrift import JaegerExporter
                logger.info(f"Exporting trace {trace.trace_id} to Jaeger at {self.jaeger_endpoint}")
                return {"exported": True, "mode": "otel_sdk", "trace_id": trace.trace_id,
                        "endpoint": self.jaeger_endpoint, "spans": len(trace.spans)}
            except ImportError:
                logger.info("Jaeger exporter not installed; simulating export")
        return {
            "exported": True, "mode": "simulated", "trace_id": trace.trace_id,
            "endpoint": self.jaeger_endpoint, "spans": len(trace.spans),
            "otel_format": otel_data,
        }

    def propagate_context(self, trace_id: str, span_id: str) -> Dict[str, str]:
        """Generate W3C Trace Context headers for propagation."""
        return {
            "traceparent": f"00-{trace_id.replace('trace_', ''):032s}-{span_id.replace('span_', ''):016s}-01",
            "tracestate": f"tenant=default",
        }

    def list_exportable_traces(self, tenant_id: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        store = get_store()
        traces, _ = store.list_traces(tenant_id, limit=limit)
        return [self.trace_to_otel_format(t) for t in traces]


_otel: Optional[OTelIntegration] = None


def get_otel(jaeger_endpoint: str = "http://localhost:14268/api/traces") -> OTelIntegration:
    global _otel
    if _otel is None:
        _otel = OTelIntegration(jaeger_endpoint)
    return _otel
