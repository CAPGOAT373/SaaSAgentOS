"""
Agent OS V6.0 - Guardrail System Models
Prompt injection protection + output filtering + policy engine
"""
import uuid
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timezone


class GuardAction(str, Enum):
    """Action to take when a guardrail rule is triggered."""
    ALLOW = "allow"        # Allow the content through
    WARN = "warn"          # Allow but log a warning
    BLOCK = "block"        # Block the content entirely
    REDACT = "redact"      # Redact sensitive parts
    SANITIZE = "sanitize"  # Sanitize/rephrase the content


class GuardSeverity(str, Enum):
    """Severity level of a guardrail violation."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GuardCategory(str, Enum):
    """Category of guardrail check."""
    INJECTION = "injection"            # Prompt injection attempt
    HARMFUL_CONTENT = "harmful_content"  # Hate speech, violence, etc.
    PII_LEAK = "pii_leak"              # Personally identifiable information
    SENSITIVE_DATA = "sensitive_data"   # API keys, secrets, tokens
    JAILBREAK = "jailbreak"            # Jailbreak attempt
    ROLE_SWITCH = "role_switch"        # Attempt to switch system role
    PROMPT_LEAK = "prompt_leak"        # Attempt to extract system prompt
    CUSTOM = "custom"                  # Custom rule


class GuardDirection(str, Enum):
    """Direction of guardrail check."""
    INPUT = "input"    # Checking user input/prompt
    OUTPUT = "output"  # Checking LLM output


@dataclass
class GuardRule:
    """A single guardrail rule."""
    rule_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    category: str = GuardCategory.CUSTOM.value
    direction: str = GuardDirection.INPUT.value  # input | output | both
    patterns: List[str] = field(default_factory=list)  # regex patterns
    keywords: List[str] = field(default_factory=list)  # keyword blacklist
    action: str = GuardAction.WARN.value
    severity: str = GuardSeverity.MEDIUM.value
    enabled: bool = True
    priority: int = 0  # higher = evaluated first
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "direction": self.direction,
            "patterns": self.patterns,
            "keywords": self.keywords,
            "action": self.action,
            "severity": self.severity,
            "enabled": self.enabled,
            "priority": self.priority,
            "metadata": self.metadata,
        }


@dataclass
class GuardViolation:
    """A detected guardrail violation."""
    violation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    rule_id: str = ""
    rule_name: str = ""
    category: str = GuardCategory.CUSTOM.value
    severity: str = GuardSeverity.MEDIUM.value
    direction: str = GuardDirection.INPUT.value
    description: str = ""
    matched_content: str = ""  # the specific content that triggered
    matched_pattern: str = ""  # the pattern that matched
    position: int = -1  # character position in content
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "violation_id": self.violation_id,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "category": self.category,
            "severity": self.severity,
            "direction": self.direction,
            "description": self.description,
            "matched_content": self.matched_content[:200],
            "matched_pattern": self.matched_pattern,
            "position": self.position,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class GuardResult:
    """Result of a guardrail evaluation."""
    passed: bool = True
    action: str = GuardAction.ALLOW.value  # final action after evaluation
    direction: str = GuardDirection.INPUT.value
    original_content: str = ""
    sanitized_content: str = ""  # content after sanitization/redaction
    violations: List[GuardViolation] = field(default_factory=list)
    total_rules_evaluated: int = 0
    total_rules_triggered: int = 0
    highest_severity: str = ""
    latency_ms: float = 0.0
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "action": self.action,
            "direction": self.direction,
            "original_content_length": len(self.original_content),
            "sanitized_content": self.sanitized_content if self.sanitized_content else "",
            "sanitized_content_length": len(self.sanitized_content) if self.sanitized_content else 0,
            "violations": [v.to_dict() for v in self.violations],
            "total_rules_evaluated": self.total_rules_evaluated,
            "total_rules_triggered": self.total_rules_triggered,
            "highest_severity": self.highest_severity,
            "latency_ms": round(self.latency_ms, 2),
            "checked_at": self.checked_at,
            "metadata": self.metadata,
        }


@dataclass
class Policy:
    """A guardrail policy: collection of rules with a default action."""
    policy_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    rules: List[GuardRule] = field(default_factory=list)
    default_action: str = GuardAction.WARN.value
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "rules": [r.to_dict() for r in self.rules],
            "default_action": self.default_action,
            "enabled": self.enabled,
            "rule_count": len(self.rules),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


@dataclass
class AuditLogEntry:
    """Audit log entry for guardrail decisions."""
    log_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    user_id: str = ""
    agent_id: str = ""
    session_id: str = ""
    direction: str = GuardDirection.INPUT.value
    content_hash: str = ""  # hash of original content (for privacy)
    content_length: int = 0
    result_action: str = GuardAction.ALLOW.value
    violations_count: int = 0
    highest_severity: str = ""
    policy_id: str = ""
    latenc_ms: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "log_id": self.log_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "direction": self.direction,
            "content_hash": self.content_hash,
            "content_length": self.content_length,
            "result_action": self.result_action,
            "violations_count": self.violations_count,
            "highest_severity": self.highest_severity,
            "policy_id": self.policy_id,
            "latency_ms": round(self.latenc_ms, 2),
            "created_at": self.created_at,
            "metadata": self.metadata,
        }