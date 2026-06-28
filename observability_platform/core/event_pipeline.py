"""
Event Pipeline - Event Sourcing for all Agent events.
Processes 8 event types: AgentStart, PromptBuild, RAGSearch, ToolCall,
LLMCall, Output, Error, Cost. Each event is persisted and routed to
the appropriate observability subsystem.
"""
import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from .models import (
    EventType, SpanStatus, LogEntry, LogLevel,
    LLMCall, ToolCall, RAGQuery, CostRecord, ErrorRecord, PromptVersion,
)
from .storage import get_store
from .trace_collector import get_collector

logger = logging.getLogger(__name__)


@dataclass
class BaseEvent:
    event_id: str = field(default_factory=lambda: f"evt_{int(time.time()*1000)}")
    trace_id: str = ""
    span_id: str = ""
    tenant_id: str = "default"
    agent_id: str = ""
    event_type: str = ""
    timestamp: float = field(default_factory=time.time)
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class EventPipeline:
    """Processes and routes observability events (Event Sourcing)."""

    def __init__(self):
        self._store = get_store()
        self._collector = get_collector()
        self._event_log: List[Dict[str, Any]] = []
        self._subscribers: Dict[str, List] = {}
        # pricing table (USD per 1K tokens)
        self._pricing = {
            "gpt-4": {"prompt": 0.03, "completion": 0.06},
            "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
            "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
            "claude-3-opus": {"prompt": 0.015, "completion": 0.075},
            "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
            "default": {"prompt": 0.002, "completion": 0.006},
        }

    def subscribe(self, event_type: str, handler):
        self._subscribers.setdefault(event_type, []).append(handler)

    def emit(self, event: BaseEvent) -> Dict[str, Any]:
        """Process an event through the pipeline."""
        result = {"event_id": event.event_id, "event_type": event.event_type, "processed": True}
        self._event_log.append(event.to_dict())

        handler_map = {
            EventType.AGENT_START.value: self._handle_agent_start,
            EventType.PROMPT_BUILD.value: self._handle_prompt_build,
            EventType.RAG_SEARCH.value: self._handle_rag_search,
            EventType.TOOL_CALL.value: self._handle_tool_call,
            EventType.LLM_CALL.value: self._handle_llm_call,
            EventType.OUTPUT.value: self._handle_output,
            EventType.ERROR.value: self._handle_error,
            EventType.COST.value: self._handle_cost,
        }
        handler = handler_map.get(event.event_type)
        if handler:
            handler_result = handler(event)
            result.update(handler_result or {})

        # notify subscribers
        for sub in self._subscribers.get(event.event_type, []):
            try:
                sub(event)
            except Exception as e:
                logger.warning(f"Subscriber error for {event.event_type}: {e}")

        # structured log
        self._store.add_log(LogEntry(
            trace_id=event.trace_id, span_id=event.span_id,
            tenant_id=event.tenant_id, level=LogLevel.INFO.value,
            message=f"Event: {event.event_type}",
            payload=event.payload,
        ))
        return result

    # ── Event handlers ──────────────────────────────────
    def _handle_agent_start(self, event: BaseEvent) -> Dict[str, Any]:
        return {"action": "trace_started"}

    def _handle_prompt_build(self, event: BaseEvent) -> Dict[str, Any]:
        pv = PromptVersion(
            tenant_id=event.tenant_id, agent_id=event.agent_id,
            prompt_name=event.payload.get("prompt_name", "default"),
            version=event.payload.get("version", "1.0.0"),
            template=event.payload.get("template", ""),
            variables=event.payload.get("variables", {}),
            rendered=event.payload.get("rendered", ""),
            output=event.payload.get("output", ""),
        )
        self._store.save_prompt_version(pv)
        return {"prompt_version_id": pv.version_id}

    def _handle_rag_search(self, event: BaseEvent) -> Dict[str, Any]:
        rq = RAGQuery(
            trace_id=event.trace_id, span_id=event.span_id,
            tenant_id=event.tenant_id, agent_id=event.agent_id,
            query=event.payload.get("query", ""),
            embedding_dim=event.payload.get("embedding_dim", 0),
            vector_search_results=event.payload.get("vector_search_results", 0),
            rerank_scores=event.payload.get("rerank_scores", []),
            retrieved_docs=event.payload.get("retrieved_docs", []),
            latency_ms=event.payload.get("latency_ms", 0.0),
        )
        self._store.save_rag_query(rq)
        return {"rag_query_id": rq.query_id}

    def _handle_tool_call(self, event: BaseEvent) -> Dict[str, Any]:
        tc = ToolCall(
            trace_id=event.trace_id, span_id=event.span_id,
            tenant_id=event.tenant_id, agent_id=event.agent_id,
            tool_name=event.payload.get("tool_name", ""),
            input=event.payload.get("input"),
            output=event.payload.get("output"),
            latency_ms=event.payload.get("latency_ms", 0.0),
            error=event.payload.get("error", ""),
            permission_granted=event.payload.get("permission_granted", True),
            status=SpanStatus.ERROR.value if event.payload.get("error") else SpanStatus.OK.value,
        )
        self._store.save_tool_call(tc)
        return {"tool_call_id": tc.call_id}

    def _handle_llm_call(self, event: BaseEvent) -> Dict[str, Any]:
        model = event.payload.get("model", "default")
        prompt_tokens = event.payload.get("prompt_tokens", 0)
        completion_tokens = event.payload.get("completion_tokens", 0)
        total_tokens = prompt_tokens + completion_tokens
        cost = self._compute_cost(model, prompt_tokens, completion_tokens)

        call = LLMCall(
            trace_id=event.trace_id, span_id=event.span_id,
            tenant_id=event.tenant_id, agent_id=event.agent_id,
            model=model, prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens, total_tokens=total_tokens,
            latency_ms=event.payload.get("latency_ms", 0.0),
            cost=cost, quality_score=event.payload.get("quality_score", 0.0),
            prompt=event.payload.get("prompt", ""),
            response=event.payload.get("response", ""),
            status=event.payload.get("status", SpanStatus.OK.value),
        )
        self._store.save_llm_call(call)

        # emit cost event
        self.emit(BaseEvent(
            trace_id=event.trace_id, span_id=event.span_id,
            tenant_id=event.tenant_id, agent_id=event.agent_id,
            event_type=EventType.COST.value,
            payload={
                "component": "llm", "model": model,
                "tokens": total_tokens, "cost": cost,
            },
        ))
        # update trace totals
        trace = self._collector.get_trace(event.trace_id)
        if trace:
            self._collector.update_trace(
                event.trace_id,
                total_tokens=trace.total_tokens + total_tokens,
                total_cost=trace.total_cost + cost,
            )
        return {"llm_call_id": call.call_id, "cost": cost}

    def _handle_output(self, event: BaseEvent) -> Dict[str, Any]:
        return {"output_captured": True}

    def _handle_error(self, event: BaseEvent) -> Dict[str, Any]:
        err = ErrorRecord(
            trace_id=event.trace_id, span_id=event.span_id,
            tenant_id=event.tenant_id, agent_id=event.agent_id,
            error_type=event.payload.get("error_type", "RuntimeError"),
            message=event.payload.get("message", ""),
            stack=event.payload.get("stack", ""),
        )
        self._store.save_error(err)
        return {"error_id": err.error_id}

    def _handle_cost(self, event: BaseEvent) -> Dict[str, Any]:
        rec = CostRecord(
            trace_id=event.trace_id, tenant_id=event.tenant_id,
            agent_id=event.agent_id,
            workflow_id=event.payload.get("workflow_id", ""),
            component=event.payload.get("component", "llm"),
            tokens=event.payload.get("tokens", 0),
            cost=event.payload.get("cost", 0.0),
        )
        self._store.save_cost_record(rec)
        return {"cost_record_id": rec.record_id}

    def _compute_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        rates = self._pricing.get(model, self._pricing["default"])
        return (prompt_tokens / 1000.0) * rates["prompt"] + (completion_tokens / 1000.0) * rates["completion"]

    def list_events(self, trace_id: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        events = self._event_log
        if trace_id:
            events = [e for e in events if e.get("trace_id") == trace_id]
        return list(reversed(events))[:limit]


_pipeline: Optional[EventPipeline] = None


def get_pipeline() -> EventPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = EventPipeline()
    return _pipeline
