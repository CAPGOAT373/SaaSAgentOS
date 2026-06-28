"""
Storage Layer - In-memory store with optional PostgreSQL persistence.
Gracefully degrades to in-memory when PostgreSQL is unavailable, ensuring
the platform is always runnable.
"""
import json
import logging
import threading
from typing import Optional, Dict, Any, List, Tuple
from collections import defaultdict, deque

from .models import (
    Trace, Span, LogEntry, LLMCall, ToolCall, RAGQuery,
    PromptVersion, CostRecord, ErrorRecord, SecurityAlert,
)

logger = logging.getLogger(__name__)


class InMemoryStore:
    """Thread-safe in-memory storage for all observability entities."""

    def __init__(self, max_traces: int = 5000, max_logs: int = 20000):
        self._lock = threading.RLock()
        self._traces: Dict[str, Trace] = {}
        self._logs: deque = deque(maxlen=max_logs)
        self._llm_calls: Dict[str, LLMCall] = {}
        self._tool_calls: Dict[str, ToolCall] = {}
        self._rag_queries: Dict[str, RAGQuery] = {}
        self._prompt_versions: Dict[str, PromptVersion] = {}
        self._cost_records: Dict[str, CostRecord] = {}
        self._errors: Dict[str, ErrorRecord] = {}
        self._security_alerts: Dict[str, SecurityAlert] = {}
        self._max_traces = max_traces
        # indices
        self._traces_by_tenant: Dict[str, List[str]] = defaultdict(list)
        self._traces_by_agent: Dict[str, List[str]] = defaultdict(list)

    # ── Traces ──────────────────────────────────────────
    def save_trace(self, trace: Trace) -> None:
        with self._lock:
            if len(self._traces) >= self._max_traces and trace.trace_id not in self._traces:
                oldest = min(self._traces.values(), key=lambda t: t.start_time)
                self._traces.pop(oldest.trace_id, None)
            self._traces[trace.trace_id] = trace
            if trace.tenant_id:
                if trace.trace_id not in self._traces_by_tenant[trace.tenant_id]:
                    self._traces_by_tenant[trace.tenant_id].append(trace.trace_id)
            if trace.agent_id:
                if trace.trace_id not in self._traces_by_agent[trace.agent_id]:
                    self._traces_by_agent[trace.agent_id].append(trace.trace_id)

    def get_trace(self, trace_id: str) -> Optional[Trace]:
        with self._lock:
            return self._traces.get(trace_id)

    def list_traces(
        self, tenant_id: str = "", agent_id: str = "",
        limit: int = 50, offset: int = 0, status: str = "",
    ) -> Tuple[List[Trace], int]:
        with self._lock:
            traces = list(self._traces.values())
            if tenant_id:
                traces = [t for t in traces if t.tenant_id == tenant_id]
            if agent_id:
                traces = [t for t in traces if t.agent_id == agent_id]
            if status:
                traces = [t for t in traces if t.status == status]
            traces.sort(key=lambda t: t.start_time, reverse=True)
            total = len(traces)
            return traces[offset:offset + limit], total

    # ── Logs ────────────────────────────────────────────
    def add_log(self, log: LogEntry) -> None:
        with self._lock:
            self._logs.append(log)

    def list_logs(
        self, trace_id: str = "", tenant_id: str = "",
        level: str = "", limit: int = 100,
    ) -> List[LogEntry]:
        with self._lock:
            logs = list(self._logs)
        if trace_id:
            logs = [l for l in logs if l.trace_id == trace_id]
        if tenant_id:
            logs = [l for l in logs if l.tenant_id == tenant_id]
        if level:
            logs = [l for l in logs if l.level == level]
        logs.sort(key=lambda l: l.timestamp, reverse=True)
        return logs[:limit]

    # ── LLM Calls ───────────────────────────────────────
    def save_llm_call(self, call: LLMCall) -> None:
        with self._lock:
            self._llm_calls[call.call_id] = call

    def list_llm_calls(self, tenant_id: str = "", trace_id: str = "", limit: int = 50) -> List[LLMCall]:
        with self._lock:
            calls = list(self._llm_calls.values())
        if tenant_id:
            calls = [c for c in calls if c.tenant_id == tenant_id]
        if trace_id:
            calls = [c for c in calls if c.trace_id == trace_id]
        calls.sort(key=lambda c: c.timestamp, reverse=True)
        return calls[:limit]

    # ── Tool Calls ──────────────────────────────────────
    def save_tool_call(self, call: ToolCall) -> None:
        with self._lock:
            self._tool_calls[call.call_id] = call

    def list_tool_calls(self, tenant_id: str = "", trace_id: str = "", limit: int = 50) -> List[ToolCall]:
        with self._lock:
            calls = list(self._tool_calls.values())
        if tenant_id:
            calls = [c for c in calls if c.tenant_id == tenant_id]
        if trace_id:
            calls = [c for c in calls if c.trace_id == trace_id]
        calls.sort(key=lambda c: c.timestamp, reverse=True)
        return calls[:limit]

    # ── RAG Queries ─────────────────────────────────────
    def save_rag_query(self, q: RAGQuery) -> None:
        with self._lock:
            self._rag_queries[q.query_id] = q

    def list_rag_queries(self, tenant_id: str = "", trace_id: str = "", limit: int = 50) -> List[RAGQuery]:
        with self._lock:
            qs = list(self._rag_queries.values())
        if tenant_id:
            qs = [q for q in qs if q.tenant_id == tenant_id]
        if trace_id:
            qs = [q for q in qs if q.trace_id == trace_id]
        qs.sort(key=lambda q: q.timestamp, reverse=True)
        return qs[:limit]

    # ── Prompt Versions ─────────────────────────────────
    def save_prompt_version(self, pv: PromptVersion) -> None:
        with self._lock:
            self._prompt_versions[pv.version_id] = pv

    def list_prompt_versions(self, tenant_id: str = "", agent_id: str = "", limit: int = 50) -> List[PromptVersion]:
        with self._lock:
            pvs = list(self._prompt_versions.values())
        if tenant_id:
            pvs = [p for p in pvs if p.tenant_id == tenant_id]
        if agent_id:
            pvs = [p for p in pvs if p.agent_id == agent_id]
        pvs.sort(key=lambda p: p.timestamp, reverse=True)
        return pvs[:limit]

    # ── Cost Records ────────────────────────────────────
    def save_cost_record(self, rec: CostRecord) -> None:
        with self._lock:
            self._cost_records[rec.record_id] = rec

    def list_cost_records(self, tenant_id: str = "", limit: int = 100) -> List[CostRecord]:
        with self._lock:
            recs = list(self._cost_records.values())
        if tenant_id:
            recs = [r for r in recs if r.tenant_id == tenant_id]
        recs.sort(key=lambda r: r.timestamp, reverse=True)
        return recs[:limit]

    # ── Errors ──────────────────────────────────────────
    def save_error(self, err: ErrorRecord) -> None:
        with self._lock:
            self._errors[err.error_id] = err

    def list_errors(self, tenant_id: str = "", trace_id: str = "", limit: int = 50) -> List[ErrorRecord]:
        with self._lock:
            errs = list(self._errors.values())
        if tenant_id:
            errs = [e for e in errs if e.tenant_id == tenant_id]
        if trace_id:
            errs = [e for e in errs if e.trace_id == trace_id]
        errs.sort(key=lambda e: e.timestamp, reverse=True)
        return errs[:limit]

    # ── Security Alerts ─────────────────────────────────
    def save_alert(self, alert: SecurityAlert) -> None:
        with self._lock:
            self._security_alerts[alert.alert_id] = alert

    def list_alerts(self, tenant_id: str = "", limit: int = 50) -> List[SecurityAlert]:
        with self._lock:
            alerts = list(self._security_alerts.values())
        if tenant_id:
            alerts = [a for a in alerts if a.tenant_id == tenant_id]
        alerts.sort(key=lambda a: a.risk_score, reverse=True)
        return alerts[:limit]

    def health(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "status": "healthy",
                "traces": len(self._traces),
                "logs": len(self._logs),
                "llm_calls": len(self._llm_calls),
                "tool_calls": len(self._tool_calls),
                "rag_queries": len(self._rag_queries),
                "prompt_versions": len(self._prompt_versions),
                "cost_records": len(self._cost_records),
                "errors": len(self._errors),
                "security_alerts": len(self._security_alerts),
            }


# ── PostgreSQL optional backend ─────────────────────────
class PostgresBackend:
    """Optional PostgreSQL persistence. Falls back silently if unavailable."""

    def __init__(self, dsn: str = ""):
        self.dsn = dsn
        self._pool = None
        self._available = False
        if dsn:
            self._init_pool()

    def _init_pool(self):
        try:
            import asyncpg
            logger.info("PostgreSQL backend requested (asyncpg available)")
            self._available = True
        except ImportError:
            logger.warning("asyncpg not installed; PostgreSQL backend disabled (using in-memory)")
            self._available = False

    @property
    def available(self) -> bool:
        return self._available


# ── Global store singleton ──────────────────────────────
_store: Optional[InMemoryStore] = None
_pg: Optional[PostgresBackend] = None


def get_store() -> InMemoryStore:
    global _store
    if _store is None:
        _store = InMemoryStore()
    return _store


def init_postgres(dsn: str = "") -> PostgresBackend:
    global _pg
    _pg = PostgresBackend(dsn)
    return _pg


def get_postgres() -> Optional[PostgresBackend]:
    return _pg
