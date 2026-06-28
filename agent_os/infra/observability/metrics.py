"""
Agent OS V6.0 - Observability System
Prometheus metrics, structured logging, health checks
"""
import time
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from agent_os.config import get_config, ObservabilityConfig

logger = logging.getLogger(__name__)


@dataclass
class Metrics:
    """Simple metrics collector (Prometheus stub)"""
    _counters: Dict[str, int] = field(default_factory=dict)
    _gauges: Dict[str, float] = field(default_factory=dict)
    _histograms: Dict[str, list] = field(default_factory=dict)
    _timers: Dict[str, list] = field(default_factory=dict)

    def increment(self, name: str, value: int = 1, tags: Optional[Dict] = None):
        key = self._tag_key(name, tags)
        self._counters[key] = self._counters.get(key, 0) + value

    def gauge(self, name: str, value: float, tags: Optional[Dict] = None):
        key = self._tag_key(name, tags)
        self._gauges[key] = value

    def histogram(self, name: str, value: float, tags: Optional[Dict] = None):
        key = self._tag_key(name, tags)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)

    def timer(self, name: str):
        return _Timer(self, name)

    def _tag_key(self, name: str, tags: Optional[Dict] = None) -> str:
        if tags:
            tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
            return f"{name}{{{tag_str}}}"
        return name

    def get_all(self) -> Dict[str, Any]:
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {k: {"count": len(v), "avg": sum(v)/len(v) if v else 0} for k, v in self._histograms.items()},
        }

    def reset(self):
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()


class _Timer:
    def __init__(self, metrics: Metrics, name: str):
        self._metrics = metrics
        self._name = name
        self._start = 0.0

    def __enter__(self):
        self._start = time.time()
        return self

    def __exit__(self, *args):
        elapsed = (time.time() - self._start) * 1000
        self._metrics.histogram(self._name + "_ms", elapsed)


class ObservabilityManager:
    """Central observability: metrics, logging, health checks"""

    def __init__(self):
        self._config = get_config().observability
        self.metrics = Metrics()
        self._start_time = time.time()

    def record_request(self, method: str, path: str, status_code: int, latency_ms: float, tenant_id: str = ""):
        self.metrics.increment("http_requests_total", tags={"method": method, "path": path, "status": str(status_code)})
        self.metrics.histogram("http_request_duration_ms", latency_ms, tags={"method": method, "path": path})
        if tenant_id:
            self.metrics.increment("tenant_requests_total", tags={"tenant_id": tenant_id})

    def record_agent_execution(self, agent_id: str, status: str, cost: float, latency_ms: float):
        self.metrics.increment("agent_executions_total", tags={"agent_id": agent_id, "status": status})
        self.metrics.histogram("agent_execution_cost", cost, tags={"agent_id": agent_id})
        self.metrics.histogram("agent_execution_duration_ms", latency_ms, tags={"agent_id": agent_id})

    def record_billing_event(self, event_type: str, amount: float, tenant_id: str = ""):
        self.metrics.increment("billing_events_total", tags={"type": event_type})
        self.metrics.histogram("billing_amount", amount, tags={"type": event_type})

    def record_plugin_execution(self, plugin_id: str, success: bool):
        self.metrics.increment("plugin_executions_total", tags={"plugin_id": plugin_id, "success": str(success).lower()})

    def get_health_status(self) -> Dict[str, Any]:
        uptime = time.time() - self._start_time
        return {
            "status": "healthy",
            "uptime_seconds": uptime,
            "version": "6.0.0",
            "metrics": self.metrics.get_all(),
        }

    def get_prometheus_metrics(self) -> str:
        """Generate Prometheus-format metrics string"""
        lines = []
        for key, value in self.metrics._counters.items():
            name = key.split("{")[0] if "{" in key else key
            lines.append(f"# HELP {name} Counter metric")
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{key} {value}")

        for key, value in self.metrics._gauges.items():
            name = key.split("{")[0] if "{" in key else key
            lines.append(f"# HELP {name} Gauge metric")
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{key} {value}")

        return "\n".join(lines) + "\n"


_observability: Optional[ObservabilityManager] = None


def get_observability() -> ObservabilityManager:
    global _observability
    if _observability is None:
        _observability = ObservabilityManager()
    return _observability