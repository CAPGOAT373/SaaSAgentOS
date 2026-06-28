"""
Log System - Structured logging for prompt/tool/RAG/LLM logs.
Layer 2 of the three-tier observability model.
"""
import logging
from typing import Optional, Dict, Any, List

from .models import LogEntry, LogLevel
from .storage import get_store

logger = logging.getLogger(__name__)


class LogSystem:
    """Structured log management with trace/span correlation."""

    def __init__(self):
        self._store = get_store()

    def log(
        self, trace_id: str, span_id: str, tenant_id: str,
        level: str, message: str, payload: Optional[Dict] = None,
    ) -> LogEntry:
        entry = LogEntry(
            trace_id=trace_id, span_id=span_id, tenant_id=tenant_id,
            level=level, message=message, payload=payload or {},
        )
        self._store.add_log(entry)
        return entry

    def info(self, trace_id: str, span_id: str, tenant_id: str, message: str, payload: Optional[Dict] = None):
        return self.log(trace_id, span_id, tenant_id, LogLevel.INFO.value, message, payload)

    def warn(self, trace_id: str, span_id: str, tenant_id: str, message: str, payload: Optional[Dict] = None):
        return self.log(trace_id, span_id, tenant_id, LogLevel.WARN.value, message, payload)

    def error(self, trace_id: str, span_id: str, tenant_id: str, message: str, payload: Optional[Dict] = None):
        return self.log(trace_id, span_id, tenant_id, LogLevel.ERROR.value, message, payload)

    def debug(self, trace_id: str, span_id: str, tenant_id: str, message: str, payload: Optional[Dict] = None):
        return self.log(trace_id, span_id, tenant_id, LogLevel.DEBUG.value, message, payload)

    def list_logs(
        self, trace_id: str = "", tenant_id: str = "",
        level: str = "", limit: int = 100,
    ) -> List[Dict[str, Any]]:
        logs = self._store.list_logs(trace_id, tenant_id, level, limit)
        return [l.to_dict() for l in logs]

    def get_prompt_logs(self, tenant_id: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        logs = self._store.list_logs(tenant_id=tenant_id, limit=limit * 10)
        return [l.to_dict() for l in logs if "prompt" in l.message.lower() or "prompt" in l.payload][:limit]

    def get_tool_logs(self, tenant_id: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        logs = self._store.list_logs(tenant_id=tenant_id, limit=limit * 10)
        return [l.to_dict() for l in logs if "tool" in l.message.lower() or "tool" in l.payload][:limit]

    def get_rag_logs(self, tenant_id: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        logs = self._store.list_logs(tenant_id=tenant_id, limit=limit * 10)
        return [l.to_dict() for l in logs if "rag" in l.message.lower() or "rag" in l.payload][:limit]

    def get_llm_logs(self, tenant_id: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        logs = self._store.list_logs(tenant_id=tenant_id, limit=limit * 10)
        return [l.to_dict() for l in logs if "llm" in l.message.lower() or "llm" in l.payload][:limit]


_log_system: Optional[LogSystem] = None


def get_log_system() -> LogSystem:
    global _log_system
    if _log_system is None:
        _log_system = LogSystem()
    return _log_system
