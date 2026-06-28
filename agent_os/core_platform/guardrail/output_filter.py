"""
Agent OS V6.0 - Output Safety Filter
Filters LLM output for harmful content, PII leaks, and sensitive data.
"""
import re
import hashlib
from typing import List, Tuple, Optional, Set
from dataclasses import dataclass, field

from agent_os.config import get_config
from .models import (
    GuardCategory, GuardSeverity, GuardDirection,
    GuardViolation,
)


# Content moderation keyword lists
HARMFUL_KEYWORDS: dict = {
    "hate_speech": [
        "hate", "kill all", "exterminate", "inferior race",
        "ethnic cleansing",
    ],
    "violence": [
        "murder", "torture", "maim", "kill yourself",
        "suicide method", "how to build a bomb",
    ],
    "sexual_content": [
        "explicit sexual", "pornography", "sexual acts",
    ],
    "self_harm": [
        "self-harm", "self harm", "cutting yourself",
        "suicide", "end my life",
    ],
    "harassment": [
        "dox", "doxx", "swat", "swatting",
    ],
    "illegal_activity": [
        "how to make drugs", "how to hack into",
        "credit card fraud", "identity theft",
    ],
    "misinformation": [
        "false flag", "conspiracy", "fake news",
    ],
}


@dataclass
class OutputFilterResult:
    """Result of output content filtering."""
    passed: bool = True
    is_safe: bool = True
    violations: List[GuardViolation] = field(default_factory=list)
    sanitized_content: str = ""
    redacted: bool = False
    matched_categories: List[str] = field(default_factory=list)


class OutputFilter:
    """
    Output Safety Filter.

    Filters:
    - Harmful content (hate speech, violence, sexual, self-harm, harassment)
    - PII/sensitive data leaks (SSN, credit cards, emails, API keys, etc.)
    - Content moderation across predefined categories
    """

    def __init__(self):
        self._config = get_config().guardrail
        self._sensitive_patterns = [
            re.compile(p) for p in self._config.sensitive_data_patterns
        ]

    def filter(self, content: str) -> OutputFilterResult:
        """
        Filter LLM output for safety and sensitive data.

        Returns OutputFilterResult with violations and sanitized content.
        """
        if not content or not self._config.output_filtering:
            return OutputFilterResult(sanitized_content=content)

        violations: List[GuardViolation] = []
        matched_categories: set = set()

        # 1. Check for harmful content
        harmful_violations, harmful_cats = self._check_harmful_content(content)
        violations.extend(harmful_violations)
        matched_categories.update(harmful_cats)

        # 2. Check for sensitive data / PII
        pii_violations, pii_cats = self._check_sensitive_data(content)
        violations.extend(pii_violations)
        matched_categories.update(pii_cats)

        # 3. Sanitize content if needed
        sanitized = content
        redacted = False

        if violations:
            # Redact sensitive data patterns
            sanitized, redacted = self._redact_content(content, violations)

        is_safe = all(
            v.severity not in (GuardSeverity.CRITICAL.value, GuardSeverity.HIGH.value)
            for v in violations
        )

        return OutputFilterResult(
            passed=len(violations) == 0,
            is_safe=is_safe,
            violations=violations,
            sanitized_content=sanitized,
            redacted=redacted,
            matched_categories=list(matched_categories),
        )

    def _check_harmful_content(self, content: str) -> Tuple[List[GuardViolation], Set[str]]:
        """Check content for harmful keywords."""
        violations = []
        matched_categories = set()
        content_lower = content.lower()

        for category, keywords in HARMFUL_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in content_lower:
                    violation = GuardViolation(
                        rule_name=f"harmful:{category}",
                        category=GuardCategory.HARMFUL_CONTENT.value,
                        severity=GuardSeverity.HIGH.value,
                        direction=GuardDirection.OUTPUT.value,
                        description=f"Detected harmful content [{category}]: matched '{keyword}'",
                        matched_content=keyword,
                        matched_pattern=keyword,
                        position=content_lower.find(keyword.lower()),
                    )
                    violations.append(violation)
                    matched_categories.add(category)

        return violations, matched_categories

    def _check_sensitive_data(self, content: str) -> Tuple[List[GuardViolation], Set[str]]:
        """Check content for sensitive data patterns (PII, secrets, API keys)."""
        violations = []
        matched_categories = set()

        for pattern in self._sensitive_patterns:
            matches = list(pattern.finditer(content))
            for match in matches:
                # Classify the type of sensitive data
                matched_text = match.group()
                pattern_str = pattern.pattern

                if "sk-" in pattern_str or "AKIA" in pattern_str:
                    category = GuardCategory.SENSITIVE_DATA.value
                    desc = f"Detected potential API key/secret: '{matched_text[:8]}...'"
                elif "@" in pattern_str:
                    category = GuardCategory.PII_LEAK.value
                    desc = f"Detected email address: '{matched_text}'"
                elif "\\d{3}-\\d{2}-\\d{4}" in pattern_str:
                    category = GuardCategory.PII_LEAK.value
                    desc = "Detected SSN pattern"
                elif "\\d{16}" in pattern_str:
                    category = GuardCategory.PII_LEAK.value
                    desc = "Detected credit card number pattern"
                elif "1[3-9]\\d{9}" in pattern_str:
                    category = GuardCategory.PII_LEAK.value
                    desc = f"Detected phone number: '{matched_text}'"
                elif "uuid" in pattern_str.lower() or "0-9a-fA-F]{8}-" in pattern_str:
                    category = GuardCategory.SENSITIVE_DATA.value
                    desc = "Detected UUID/token pattern"
                else:
                    category = GuardCategory.SENSITIVE_DATA.value
                    desc = f"Detected sensitive data pattern: '{matched_text[:20]}...'"

                violation = GuardViolation(
                    rule_name=f"sensitive:{category}",
                    category=category,
                    severity=GuardSeverity.HIGH.value,
                    direction=GuardDirection.OUTPUT.value,
                    description=desc,
                    matched_content=matched_text[:50],
                    matched_pattern=pattern_str,
                    position=match.start(),
                )
                violations.append(violation)
                matched_categories.add(category)

        return violations, matched_categories

    def _redact_content(self, content: str, violations: List[GuardViolation]) -> Tuple[str, bool]:
        """
        Redact sensitive content by replacing matched patterns with [REDACTED].

        Returns (sanitized_content, was_redacted).
        """
        result = content
        redacted = False

        # Collect unique patterns and their replacements
        for violation in violations:
            if violation.matched_content and violation.matched_content in result:
                if violation.category == GuardCategory.PII_LEAK.value:
                    replacement = "[REDACTED_PII]"
                elif violation.category == GuardCategory.SENSITIVE_DATA.value:
                    replacement = "[REDACTED_SECRET]"
                else:
                    replacement = "[REDACTED]"

                result = result.replace(violation.matched_content, replacement)
                redacted = True

        return result, redacted

    def hash_content(self, content: str) -> str:
        """Create a SHA256 hash of content for audit logging."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


# Singleton
_output_filter: Optional[OutputFilter] = None


def get_output_filter() -> OutputFilter:
    global _output_filter
    if _output_filter is None:
        _output_filter = OutputFilter()
    return _output_filter