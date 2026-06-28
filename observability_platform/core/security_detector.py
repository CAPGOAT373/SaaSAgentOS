"""
AI Security Detector - Detects prompt injection, tool misuse, data leakage,
and unauthorized access. Outputs risk score (0-100), alert level, and auto-block decision.
"""
import re
import logging
from typing import Optional, Dict, Any, List

from .models import SecurityAlert, AlertLevel
from .storage import get_store
from .trace_collector import get_collector

logger = logging.getLogger(__name__)


class SecurityDetector:
    """AI security observation: risk detection and alerting."""

    # prompt injection patterns
    INJECTION_PATTERNS = [
        r"(?i)ignore\s+(all\s+)?previous\s+instructions",
        r"(?i)disregard\s+(the\s+)?(above|previous|prior)",
        r"(?i)you\s+are\s+now\s+(a|an)\s+\w+",
        r"(?i)forget\s+(everything|all\s+rules)",
        r"(?i)reveal\s+(your|the)\s+(system\s+)?prompt",
        r"(?i)jailbreak",
        r"(?i)override\s+(safety|security|content\s+filter)",
        r"(?i)act\s+as\s+(if\s+)?(you\s+have\s+no|without)\s+restrictions",
        r"(?i)pretend\s+(you\s+are|to\s+be)\s+(dan|evil|unrestricted)",
        r"(?i)\\u00[0-9a-f]{2}",  # unicode escape attempts
    ]

    # sensitive data patterns
    LEAKAGE_PATTERNS = [
        r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
        r"\b\d{16}\b",  # credit card
        r"(?i)password\s*[:=]\s*\S+",
        r"(?i)api[_-]?key\s*[:=]\s*\S+",
        r"(?i)secret\s*[:=]\s*\S+",
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # email
        r"(?i)Bearer\s+[A-Za-z0-9\-\._~+\/=]+",
    ]

    # dangerous tool operations
    DANGEROUS_TOOLS = ["exec", "eval", "shell", "subprocess", "rm", "delete", "drop", "format"]

    def __init__(self):
        self._store = get_store()
        self._collector = get_collector()

    def analyze_prompt(self, prompt: str, trace_id: str = "", tenant_id: str = "", agent_id: str = "") -> Dict[str, Any]:
        """Analyze a prompt for injection attempts."""
        risks = []
        score = 0

        for pattern in self.INJECTION_PATTERNS:
            matches = re.findall(pattern, prompt)
            if matches:
                risks.append({"type": "prompt_injection", "pattern": pattern, "matches": len(matches)})
                score += 25

        # data leakage in prompt
        for pattern in self.LEAKAGE_PATTERNS:
            matches = re.findall(pattern, prompt)
            if matches:
                risks.append({"type": "data_leakage", "pattern": pattern, "matches": len(matches)})
                score += 20

        score = min(score, 100)
        level = self._score_to_level(score)
        auto_block = score >= 70

        result = {
            "risk_score": score, "alert_level": level, "auto_block": auto_block,
            "risks": risks, "analyzed": True,
        }

        if risks and trace_id:
            alert = SecurityAlert(
                trace_id=trace_id, tenant_id=tenant_id, agent_id=agent_id,
                risk_type="prompt_injection", risk_score=score,
                alert_level=level, auto_block=auto_block,
                detail=f"Detected {len(risks)} risk(s) in prompt",
                evidence={"risks": risks, "prompt_snippet": prompt[:200]},
            )
            self._store.save_alert(alert)
            self._collector.update_trace(trace_id, risk_score=score, alert_level=level)
        return result

    def analyze_tool_call(
        self, tool_name: str, tool_input: Any, tool_output: Any,
        permission_granted: bool, trace_id: str = "", tenant_id: str = "", agent_id: str = "",
    ) -> Dict[str, Any]:
        """Analyze a tool call for misuse."""
        risks = []
        score = 0

        if not permission_granted:
            risks.append({"type": "unauthorized_access", "detail": "Tool called without permission"})
            score += 60

        name_lower = tool_name.lower()
        for danger in self.DANGEROUS_TOOLS:
            if danger in name_lower:
                risks.append({"type": "tool_misuse", "tool": tool_name, "dangerous_op": danger})
                score += 30
                break

        # check output for leakage
        output_str = str(tool_output or "")
        for pattern in self.LEAKAGE_PATTERNS:
            matches = re.findall(pattern, output_str)
            if matches:
                risks.append({"type": "data_leakage", "source": "tool_output", "matches": len(matches)})
                score += 25

        score = min(score, 100)
        level = self._score_to_level(score)
        auto_block = score >= 70

        result = {
            "risk_score": score, "alert_level": level, "auto_block": auto_block,
            "risks": risks, "tool_name": tool_name,
        }

        if risks and trace_id:
            alert = SecurityAlert(
                trace_id=trace_id, tenant_id=tenant_id, agent_id=agent_id,
                risk_type="tool_misuse", risk_score=score,
                alert_level=level, auto_block=auto_block,
                detail=f"Tool '{tool_name}' flagged: {len(risks)} risk(s)",
                evidence={"risks": risks},
            )
            self._store.save_alert(alert)
            self._collector.update_trace(trace_id, risk_score=score, alert_level=level)
        return result

    def analyze_output(self, output: str, trace_id: str = "", tenant_id: str = "", agent_id: str = "") -> Dict[str, Any]:
        """Analyze LLM output for data leakage."""
        risks = []
        score = 0
        for pattern in self.LEAKAGE_PATTERNS:
            matches = re.findall(pattern, output)
            if matches:
                risks.append({"type": "data_leakage", "pattern": pattern, "matches": len(matches)})
                score += 30
        score = min(score, 100)
        level = self._score_to_level(score)
        auto_block = score >= 70

        if risks and trace_id:
            alert = SecurityAlert(
                trace_id=trace_id, tenant_id=tenant_id, agent_id=agent_id,
                risk_type="data_leakage", risk_score=score,
                alert_level=level, auto_block=auto_block,
                detail=f"Output contains {len(risks)} leakage risk(s)",
                evidence={"risks": risks},
            )
            self._store.save_alert(alert)
            self._collector.update_trace(trace_id, risk_score=score, alert_level=level)
        return {
            "risk_score": score, "alert_level": level, "auto_block": auto_block, "risks": risks,
        }

    def list_alerts(self, tenant_id: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        alerts = self._store.list_alerts(tenant_id, limit)
        return [a.to_dict() for a in alerts]

    def _score_to_level(self, score: float) -> str:
        if score >= 70:
            return AlertLevel.CRITICAL.value
        if score >= 50:
            return AlertLevel.HIGH.value
        if score >= 25:
            return AlertLevel.MEDIUM.value
        if score > 0:
            return AlertLevel.LOW.value
        return AlertLevel.NONE.value


_security: Optional[SecurityDetector] = None


def get_security_detector() -> SecurityDetector:
    global _security
    if _security is None:
        _security = SecurityDetector()
    return _security
