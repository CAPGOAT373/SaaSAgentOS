"""
Agent OS V6.0 - Prompt Injection Detector
Detects prompt injection, jailbreak, role-switching, and prompt leak attempts.
"""
import re
import hashlib
from typing import List, Tuple, Optional
from dataclasses import dataclass, field

from agent_os.config import get_config
from .models import (
    GuardCategory, GuardSeverity, GuardDirection,
    GuardViolation,
)


@dataclass
class InjectionRisk:
    """Risk assessment for prompt injection."""
    score: float = 0.0  # 0.0 - 1.0
    level: str = GuardSeverity.LOW.value
    violations: List[GuardViolation] = field(default_factory=list)
    matched_categories: List[str] = field(default_factory=list)


class InjectionDetector:
    """
    Prompt Injection Detector.

    Detects:
    - Directive override (ignore previous instructions, new rules, etc.)
    - Jailbreak attempts (DAN, role-playing as unrestricted)
    - System prompt extraction (reveal system prompt, etc.)
    - Role switching (pretend to be, act as, etc.)
    - Special token injection ([/INST], <|im_start|>, <<SYS>>, etc.)
    - Instruction manipulation (you must, do not follow, etc.)
    """

    def __init__(self):
        self._config = get_config().guardrail

    def detect(self, content: str) -> InjectionRisk:
        """
        Analyze content for prompt injection attempts.

        Returns InjectionRisk with score, severity level, and violations.
        """
        if not content or not self._config.injection_detection:
            return InjectionRisk()

        violations: List[GuardViolation] = []
        matched_categories: set = set()

        for pattern in self._config.injection_patterns:
            matches = list(re.finditer(pattern, content, re.IGNORECASE))
            for match in matches:
                category = self._classify_pattern(pattern)
                severity = self._severity_for_category(category)

                violation = GuardViolation(
                    rule_name=f"injection:{category}",
                    category=category,
                    severity=severity,
                    direction=GuardDirection.INPUT.value,
                    description=f"Detected potential {category.replace('_', ' ')}: '{match.group()}'",
                    matched_content=match.group(),
                    matched_pattern=pattern,
                    position=match.start(),
                )
                violations.append(violation)
                matched_categories.add(category)

        # Calculate risk score based on violations
        score = self._calculate_score(violations)
        level = self._severity_from_score(score)

        return InjectionRisk(
            score=score,
            level=level,
            violations=violations,
            matched_categories=list(matched_categories),
        )

    def _classify_pattern(self, pattern: str) -> str:
        """Classify a regex pattern into a guardrail category."""
        if "ignore" in pattern or "forget" in pattern or "override" in pattern:
            return GuardCategory.INJECTION.value
        if "DAN" in pattern or "jailbreak" in pattern or "unfiltered" in pattern:
            return GuardCategory.JAILBREAK.value
        if "pretend" in pattern or "act" in pattern or "roleplay" in pattern:
            return GuardCategory.ROLE_SWITCH.value
        if "reveal" in pattern or "system" in pattern:
            return GuardCategory.PROMPT_LEAK.value
        if "INST" in pattern or "im_start" in pattern or "SYS" in pattern:
            return GuardCategory.INJECTION.value
        return GuardCategory.INJECTION.value

    def _severity_for_category(self, category: str) -> str:
        """Map category to default severity."""
        mapping = {
            GuardCategory.JAILBREAK.value: GuardSeverity.CRITICAL.value,
            GuardCategory.INJECTION.value: GuardSeverity.HIGH.value,
            GuardCategory.ROLE_SWITCH.value: GuardSeverity.HIGH.value,
            GuardCategory.PROMPT_LEAK.value: GuardSeverity.MEDIUM.value,
        }
        return mapping.get(category, GuardSeverity.MEDIUM.value)

    def _calculate_score(self, violations: List[GuardViolation]) -> float:
        """Calculate overall risk score from violations."""
        if not violations:
            return 0.0

        severity_weights = {
            GuardSeverity.LOW.value: 0.15,
            GuardSeverity.MEDIUM.value: 0.35,
            GuardSeverity.HIGH.value: 0.65,
            GuardSeverity.CRITICAL.value: 0.95,
        }

        total_weight = 0.0
        count = 0
        for v in violations:
            total_weight += severity_weights.get(v.severity, 0.35)
            count += 1

        # Base score from violations, capped at 1.0
        base_score = min(total_weight / max(count, 1), 1.0)

        # Bonus for multiple violations
        if count >= 3:
            base_score = min(base_score + 0.15, 1.0)
        if count >= 5:
            base_score = min(base_score + 0.10, 1.0)

        return round(base_score, 2)

    def _severity_from_score(self, score: float) -> str:
        """Convert risk score to severity level."""
        if score >= 0.8:
            return GuardSeverity.CRITICAL.value
        elif score >= 0.6:
            return GuardSeverity.HIGH.value
        elif score >= 0.3:
            return GuardSeverity.MEDIUM.value
        return GuardSeverity.LOW.value

    def hash_content(self, content: str) -> str:
        """Create a SHA256 hash of content for audit logging."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


# Singleton
_injection_detector: Optional[InjectionDetector] = None


def get_injection_detector() -> InjectionDetector:
    global _injection_detector
    if _injection_detector is None:
        _injection_detector = InjectionDetector()
    return _injection_detector