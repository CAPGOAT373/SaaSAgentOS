"""
Metrics Engine - Computes token usage, latency, cost, error rate, tool call counts,
all segmented by tenant. Layer 1 of the three-tier observability model.
"""
import time
import logging
from typing import Optional, Dict, Any, List
from collections import defaultdict

from .storage import get_store

logger = logging.getLogger(__name__)


class MetricsEngine:
    """Aggregates metrics across traces, LLM calls, tool calls, costs, errors."""

    def __init__(self):
        self._store = get_store()

    def get_overview(self, tenant_id: str = "") -> Dict[str, Any]:
        traces, total = self._store.list_traces(tenant_id, limit=10000)
        completed = [t for t in traces if t.end_time > 0]
        durations = sorted([(t.end_time - t.start_time) * 1000 for t in completed])

        total_tokens = sum(t.total_tokens for t in traces)
        total_cost = sum(t.total_cost for t in traces)
        error_traces = sum(1 for t in traces if t.error_count > 0)

        return {
            "total_traces": total,
            "completed_traces": len(completed),
            "active_traces": sum(1 for t in traces if t.end_time == 0),
            "error_traces": error_traces,
            "error_rate": error_traces / total if total else 0.0,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "avg_latency_ms": sum(durations) / len(durations) if durations else 0,
            "p50_latency_ms": durations[len(durations) // 2] if durations else 0,
            "p95_latency_ms": durations[int(len(durations) * 0.95)] if len(durations) > 1 else (durations[0] if durations else 0),
            "p99_latency_ms": durations[int(len(durations) * 0.99)] if len(durations) > 1 else (durations[0] if durations else 0),
        }

    def get_token_stats(self, tenant_id: str = "") -> Dict[str, Any]:
        calls = self._store.list_llm_calls(tenant_id, limit=10000)
        by_model: Dict[str, Dict[str, int]] = defaultdict(lambda: {"prompt": 0, "completion": 0, "total": 0, "calls": 0})
        for c in calls:
            m = by_model[c.model]
            m["prompt"] += c.prompt_tokens
            m["completion"] += c.completion_tokens
            m["total"] += c.total_tokens
            m["calls"] += 1
        return {
            "total_tokens": sum(c.total_tokens for c in calls),
            "total_prompt_tokens": sum(c.prompt_tokens for c in calls),
            "total_completion_tokens": sum(c.completion_tokens for c in calls),
            "total_calls": len(calls),
            "by_model": dict(by_model),
        }

    def get_latency_stats(self, tenant_id: str = "") -> Dict[str, Any]:
        traces, _ = self._store.list_traces(tenant_id, limit=10000)
        completed = [t for t in traces if t.end_time > 0]
        durations = sorted([(t.end_time - t.start_time) * 1000 for t in completed])
        # span-level latency by type
        by_type: Dict[str, List[float]] = defaultdict(list)
        for t in completed:
            for s in t.spans:
                if s.duration_ms > 0:
                    by_type[s.type].append(s.duration_ms)
        type_stats = {}
        for k, vals in by_type.items():
            vals.sort()
            type_stats[k] = {
                "count": len(vals),
                "avg_ms": sum(vals) / len(vals) if vals else 0,
                "p50_ms": vals[len(vals) // 2] if vals else 0,
                "p95_ms": vals[int(len(vals) * 0.95)] if len(vals) > 1 else (vals[0] if vals else 0),
            }
        return {
            "trace_count": len(completed),
            "avg_ms": sum(durations) / len(durations) if durations else 0,
            "p50_ms": durations[len(durations) // 2] if durations else 0,
            "p95_ms": durations[int(len(durations) * 0.95)] if len(durations) > 1 else (durations[0] if durations else 0),
            "p99_ms": durations[int(len(durations) * 0.99)] if len(durations) > 1 else (durations[0] if durations else 0),
            "min_ms": durations[0] if durations else 0,
            "max_ms": durations[-1] if durations else 0,
            "by_span_type": type_stats,
        }

    def get_error_stats(self, tenant_id: str = "") -> Dict[str, Any]:
        errors = self._store.list_errors(tenant_id, limit=10000)
        by_type: Dict[str, int] = defaultdict(int)
        for e in errors:
            by_type[e.error_type] += 1
        traces, total = self._store.list_traces(tenant_id, limit=10000)
        error_traces = sum(1 for t in traces if t.error_count > 0)
        return {
            "total_errors": len(errors),
            "error_traces": error_traces,
            "error_rate": error_traces / total if total else 0,
            "by_type": dict(by_type),
        }

    def get_tool_stats(self, tenant_id: str = "") -> Dict[str, Any]:
        calls = self._store.list_tool_calls(tenant_id, limit=10000)
        by_tool: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"calls": 0, "errors": 0, "total_latency_ms": 0.0})
        for c in calls:
            t = by_tool[c.tool_name]
            t["calls"] += 1
            if c.error:
                t["errors"] += 1
            t["total_latency_ms"] += c.latency_ms
        result = {}
        for name, stats in by_tool.items():
            result[name] = {
                "calls": stats["calls"],
                "errors": stats["errors"],
                "error_rate": stats["errors"] / stats["calls"] if stats["calls"] else 0,
                "avg_latency_ms": stats["total_latency_ms"] / stats["calls"] if stats["calls"] else 0,
            }
        return {"total_tool_calls": len(calls), "by_tool": result}

    def get_tenant_usage(self, tenant_id: str = "") -> Dict[str, Any]:
        traces, _ = self._store.list_traces(tenant_id, limit=10000)
        return {
            "tenant_id": tenant_id or "all",
            "traces": len(traces),
            "tokens": sum(t.total_tokens for t in traces),
            "cost_usd": round(sum(t.total_cost for t in traces), 6),
            "errors": sum(t.error_count for t in traces),
        }

    def get_latency_heatmap(self, tenant_id: str = "") -> Dict[str, Any]:
        """Latency heatmap data: buckets of latency vs time."""
        traces, _ = self._store.list_traces(tenant_id, limit=1000)
        buckets = defaultdict(int)
        for t in traces:
            if t.end_time > 0:
                dur = (t.end_time - t.start_time) * 1000
                bucket = int(dur // 100) * 100  # 100ms buckets
                buckets[bucket] += 1
        return {
            "buckets": [{"latency_ms": k, "count": v} for k, v in sorted(buckets.items())],
        }


_metrics: Optional[MetricsEngine] = None


def get_metrics_engine() -> MetricsEngine:
    global _metrics
    if _metrics is None:
        _metrics = MetricsEngine()
    return _metrics
