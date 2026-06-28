"""
Replay Engine - Supports two replay modes:
  Mode A (Exact):   Fully reproduce the original trace execution.
  Mode B (Debug):   Re-execute with replaced prompt/model, produce diff comparison.
"""
import time
import logging
import difflib
from typing import Optional, Dict, Any, List

from .models import Trace, Span, SpanType, SpanStatus, EventType
from .storage import get_store
from .trace_collector import get_collector
from .event_pipeline import get_pipeline, BaseEvent

logger = logging.getLogger(__name__)


class ReplayEngine:
    """Trace replay with exact reproduction and debug-mode substitution."""

    def __init__(self):
        self._store = get_store()
        self._collector = get_collector()
        self._pipeline = get_pipeline()

    def exact_replay(self, trace_id: str, tenant_id: str = "") -> Dict[str, Any]:
        """Mode A: Exact replay - reproduce the original trace step by step."""
        original = self._store.get_trace(trace_id)
        if not original:
            return {"error": "Trace not found", "trace_id": trace_id}

        # create a new replay trace
        replay_trace = self._collector.start_trace(
            name=f"REPLAY(exact):{original.name}",
            tenant_id=tenant_id or original.tenant_id,
            agent_id=original.agent_id,
            metadata={"replay_of": trace_id, "mode": "exact"},
        )

        steps = []
        for span in sorted(original.spans, key=lambda s: s.start_time):
            replay_span = self._collector.start_span(
                trace_id=replay_trace.trace_id, name=span.name,
                span_type=span.type, service=span.service,
                parent_span_id=span.parent_span_id, tags=span.tags,
                input_data=span.input,
            )
            # simulate execution timing (use original duration, but cap for live replay)
            time.sleep(min(span.duration_ms / 10000.0, 0.05))
            self._collector.end_span(
                replay_span.span_id, status=span.status, output=span.output,
                metadata={"original_span_id": span.span_id, "original_duration_ms": span.duration_ms},
            )
            steps.append({
                "step": len(steps) + 1,
                "span_name": span.name,
                "type": span.type,
                "status": span.status,
                "original_duration_ms": span.duration_ms,
                "replayed": True,
            })

        self._collector.end_trace(replay_trace.trace_id, status=original.status)
        return {
            "mode": "exact",
            "original_trace_id": trace_id,
            "replay_trace_id": replay_trace.trace_id,
            "steps": steps,
            "total_steps": len(steps),
            "match": True,
        }

    def debug_replay(
        self, trace_id: str, tenant_id: str = "",
        new_prompt: str = "", new_model: str = "",
    ) -> Dict[str, Any]:
        """Mode B: Debug replay - substitute prompt/model and produce diff."""
        original = self._store.get_trace(trace_id)
        if not original:
            return {"error": "Trace not found", "trace_id": trace_id}

        replay_trace = self._collector.start_trace(
            name=f"REPLAY(debug):{original.name}",
            tenant_id=tenant_id or original.tenant_id,
            agent_id=original.agent_id,
            metadata={"replay_of": trace_id, "mode": "debug",
                      "new_prompt": bool(new_prompt), "new_model": new_model},
        )

        steps = []
        diffs = []
        original_outputs: List[str] = []
        replay_outputs: List[str] = []

        for span in sorted(original.spans, key=lambda s: s.start_time):
            # apply substitutions
            span_input = span.input
            span_tags = dict(span.tags)
            if new_prompt and span.type == SpanType.PROMPT.value:
                span_input = new_prompt
                span_tags["replaced_prompt"] = True
            if new_model and span.type == SpanType.LLM.value:
                span_tags["original_model"] = span_tags.get("model", "")
                span_tags["model"] = new_model

            replay_span = self._collector.start_span(
                trace_id=replay_trace.trace_id, name=span.name,
                span_type=span.type, service=span.service,
                parent_span_id=span.parent_span_id, tags=span_tags,
                input_data=span_input,
            )

            # simulate output (in real system, would call LLM with new params)
            replay_output = span.output
            if new_model and span.type == SpanType.LLM.value:
                replay_output = f"[debug-replay with {new_model}] {span.output or ''}"

            time.sleep(min(span.duration_ms / 10000.0, 0.02))
            self._collector.end_span(
                replay_span.span_id, status=span.status, output=replay_output,
                metadata={"original_span_id": span.span_id},
            )

            # compute diff for outputs
            orig_out = str(span.output or "")
            new_out = str(replay_output or "")
            if orig_out != new_out:
                diff = list(difflib.unified_diff(
                    orig_out.splitlines(keepends=True),
                    new_out.splitlines(keepends=True),
                    fromfile="original", tofile="replay", lineterm="",
                ))
                diffs.append({
                    "span_name": span.name,
                    "span_type": span.type,
                    "diff": "".join(diff),
                    "changed": True,
                })
            original_outputs.append(orig_out)
            replay_outputs.append(new_out)

            steps.append({
                "step": len(steps) + 1,
                "span_name": span.name,
                "type": span.type,
                "substituted": bool(new_prompt and span.type == SpanType.PROMPT.value) or bool(new_model and span.type == SpanType.LLM.value),
            })

        self._collector.end_trace(replay_trace.trace_id, status=original.status)

        # prompt diff
        prompt_diff = ""
        if new_prompt:
            original_prompt = next((str(s.input or "") for s in original.spans if s.type == SpanType.PROMPT.value), "")
            prompt_diff = "".join(difflib.unified_diff(
                original_prompt.splitlines(keepends=True),
                new_prompt.splitlines(keepends=True),
                fromfile="original_prompt", tofile="new_prompt", lineterm="",
            ))

        return {
            "mode": "debug",
            "original_trace_id": trace_id,
            "replay_trace_id": replay_trace.trace_id,
            "substitutions": {"new_prompt": new_prompt, "new_model": new_model},
            "steps": steps,
            "total_steps": len(steps),
            "output_diffs": diffs,
            "prompt_diff": prompt_diff,
            "changed_spans": len(diffs),
        }

    def step_by_step(self, trace_id: str) -> Dict[str, Any]:
        """Return trace as step-by-step execution for debugging."""
        trace = self._store.get_trace(trace_id)
        if not trace:
            return {"error": "Trace not found"}
        steps = []
        for i, span in enumerate(sorted(trace.spans, key=lambda s: s.start_time), 1):
            steps.append({
                "step": i,
                "span_id": span.span_id,
                "name": span.name,
                "type": span.type,
                "status": span.status,
                "duration_ms": span.duration_ms,
                "input": span.input,
                "output": span.output,
                "tags": span.tags,
                "events": span.events,
            })
        return {
            "trace_id": trace_id,
            "name": trace.name,
            "total_steps": len(steps),
            "steps": steps,
        }


_replay: Optional[ReplayEngine] = None


def get_replay_engine() -> ReplayEngine:
    global _replay
    if _replay is None:
        _replay = ReplayEngine()
    return _replay
