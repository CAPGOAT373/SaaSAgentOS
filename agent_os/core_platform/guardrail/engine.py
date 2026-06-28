"""
Agent OS V6.0 - Guardrail Policy Engine
Core engine that evaluates policies against content (input/output).
"""
import time
import hashlib
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone

from agent_os.config import get_config
from .models import (
    GuardAction, GuardSeverity, GuardCategory, GuardDirection,
    GuardRule, GuardViolation, GuardResult, Policy, AuditLogEntry,
)
from .injection_detector import InjectionDetector, InjectionRisk, get_injection_detector
from .output_filter import OutputFilter, OutputFilterResult, get_output_filter


class GuardrailEngine:
    """
    Guardrail Policy Engine.

    Evaluates content against:
    1. Built-in injection detection (prompt injection, jailbreak, role-switch)
    2. Built-in output filtering (harmful content, PII, sensitive data)
    3. Custom policies with user-defined rules

    Pipeline:
    content → injection_detector → output_filter → custom_rules → GuardResult
    """

    def __init__(self):
        self._config = get_config().guardrail
        self._injection_detector: Optional[InjectionDetector] = None
        self._output_filter: Optional[OutputFilter] = None
        self._policies: Dict[str, Policy] = {}
        self._audit_logs: List[AuditLogEntry] = []
        self._default_policy: Optional[Policy] = None

        # Stats
        self._total_checks: int = 0
        self._total_blocks: int = 0
        self._total_warns: int = 0
        self._total_allows: int = 0

    async def _ensure_detectors(self):
        """Lazy initialization of detectors."""
        if self._injection_detector is None:
            self._injection_detector = get_injection_detector()
        if self._output_filter is None:
            self._output_filter = get_output_filter()

    # ── Policy Management ────────────────────────────

    def add_policy(self, policy: Policy) -> Policy:
        """Add or update a guardrail policy."""
        self._policies[policy.policy_id] = policy
        return policy

    def get_policy(self, policy_id: str) -> Optional[Policy]:
        """Get a policy by ID."""
        return self._policies.get(policy_id)

    def list_policies(self) -> List[Policy]:
        """List all policies."""
        return list(self._policies.values())

    def delete_policy(self, policy_id: str) -> bool:
        """Delete a policy by ID."""
        if policy_id in self._policies:
            del self._policies[policy_id]
            return True
        return False

    def set_default_policy(self, policy: Policy):
        """Set the default policy to apply when no specific policy is specified."""
        self._default_policy = policy

    # ── Core Validation ─────────────────────────────

    async def validate_prompt(
        self,
        content: str,
        tenant_id: str = "",
        user_id: str = "",
        agent_id: str = "",
        session_id: str = "",
        policy_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GuardResult:
        """
        Validate user prompt (input) before sending to LLM.

        Checks:
        - Prompt injection detection
        - Custom input rules
        - Length limits
        """
        if not self._config.enabled:
            return GuardResult(
                passed=True,
                action=GuardAction.ALLOW.value,
                direction=GuardDirection.INPUT.value,
                original_content=content,
            )

        await self._ensure_detectors()
        start_time = time.time()
        violations: List[GuardViolation] = []
        rules_evaluated = 0

        # 1. Length check
        if len(content) > self._config.max_prompt_length:
            violations.append(GuardViolation(
                rule_name="length_limit",
                category=GuardCategory.CUSTOM.value,
                severity=GuardSeverity.LOW.value,
                direction=GuardDirection.INPUT.value,
                description=f"Prompt exceeds max length: {len(content)} > {self._config.max_prompt_length}",
                matched_content=content[:100],
            ))
        rules_evaluated += 1

        # 2. Injection detection
        if self._config.injection_detection:
            risk = self._injection_detector.detect(content)
            if risk.violations:
                violations.extend(risk.violations)
            rules_evaluated += len(self._config.injection_patterns)

        # 3. Custom policy rules
        policy = self._get_policy(policy_id)
        if policy and policy.enabled:
            custom_violations, custom_evaluated = self._evaluate_rules(
                content, policy.rules, GuardDirection.INPUT.value
            )
            violations.extend(custom_violations)
            rules_evaluated += custom_evaluated

        # 4. Determine action
        action = self._determine_action(violations)
        highest_severity = self._highest_severity(violations)

        # 5. Audit log
        if self._config.audit_log_enabled:
            self._log_audit(
                tenant_id=tenant_id, user_id=user_id, agent_id=agent_id,
                session_id=session_id, direction=GuardDirection.INPUT.value,
                content=content, action=action, violations_count=len(violations),
                highest_severity=highest_severity, policy_id=policy_id,
                latency_ms=(time.time() - start_time) * 1000,
            )

        # 6. Update stats
        self._update_stats(action)

        return GuardResult(
            passed=action not in (GuardAction.BLOCK.value,),
            action=action,
            direction=GuardDirection.INPUT.value,
            original_content=content,
            violations=violations,
            total_rules_evaluated=rules_evaluated,
            total_rules_triggered=len(violations),
            highest_severity=highest_severity,
            latency_ms=(time.time() - start_time) * 1000,
            metadata=metadata or {},
        )

    async def validate_output(
        self,
        content: str,
        tenant_id: str = "",
        user_id: str = "",
        agent_id: str = "",
        session_id: str = "",
        policy_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GuardResult:
        """
        Validate LLM output before returning to user.

        Checks:
        - Harmful content filtering
        - PII/sensitive data detection
        - Custom output rules
        - Length limits
        """
        if not self._config.enabled:
            return GuardResult(
                passed=True,
                action=GuardAction.ALLOW.value,
                direction=GuardDirection.OUTPUT.value,
                original_content=content,
                sanitized_content=content,
            )

        await self._ensure_detectors()
        start_time = time.time()
        violations: List[GuardViolation] = []
        rules_evaluated = 0
        sanitized = content

        # 1. Length check
        if len(content) > self._config.max_output_length:
            violations.append(GuardViolation(
                rule_name="length_limit",
                category=GuardCategory.CUSTOM.value,
                severity=GuardSeverity.LOW.value,
                direction=GuardDirection.OUTPUT.value,
                description=f"Output exceeds max length: {len(content)} > {self._config.max_output_length}",
            ))
        rules_evaluated += 1

        # 2. Output filtering
        if self._config.output_filtering:
            filter_result = self._output_filter.filter(content)
            if filter_result.violations:
                violations.extend(filter_result.violations)
            if filter_result.redacted:
                sanitized = filter_result.sanitized_content
            rules_evaluated += 1

        # 3. Custom policy rules
        policy = self._get_policy(policy_id)
        if policy and policy.enabled:
            custom_violations, custom_evaluated = self._evaluate_rules(
                content, policy.rules, GuardDirection.OUTPUT.value
            )
            violations.extend(custom_violations)
            rules_evaluated += custom_evaluated

        # 4. Determine action - redact if PII/sensitive data found
        # PII/Sensitive data REDACT takes priority over BLOCK (redaction is more appropriate)
        has_pii = any(
            v.category == GuardCategory.PII_LEAK.value for v in violations
        )
        has_sensitive = any(
            v.category == GuardCategory.SENSITIVE_DATA.value for v in violations
        )
        if has_pii or has_sensitive:
            action = GuardAction.REDACT.value
        else:
            action = self._determine_action(violations)

        highest_severity = self._highest_severity(violations)

        # 5. Audit log
        if self._config.audit_log_enabled:
            self._log_audit(
                tenant_id=tenant_id, user_id=user_id, agent_id=agent_id,
                session_id=session_id, direction=GuardDirection.OUTPUT.value,
                content=content, action=action, violations_count=len(violations),
                highest_severity=highest_severity, policy_id=policy_id,
                latency_ms=(time.time() - start_time) * 1000,
            )

        # 6. Update stats
        self._update_stats(action)

        return GuardResult(
            passed=action not in (GuardAction.BLOCK.value,),
            action=action,
            direction=GuardDirection.OUTPUT.value,
            original_content=content,
            sanitized_content=sanitized,
            violations=violations,
            total_rules_evaluated=rules_evaluated,
            total_rules_triggered=len(violations),
            highest_severity=highest_severity,
            latency_ms=(time.time() - start_time) * 1000,
            metadata=metadata or {},
        )

    async def validate_full_cycle(
        self,
        prompt: str,
        output: str,
        tenant_id: str = "",
        user_id: str = "",
        agent_id: str = "",
        session_id: str = "",
        policy_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validate both prompt and output in a single call.
        Returns combined results for the full LLM interaction cycle.
        """
        prompt_result = await self.validate_prompt(
            content=prompt, tenant_id=tenant_id, user_id=user_id,
            agent_id=agent_id, session_id=session_id, policy_id=policy_id,
        )
        output_result = await self.validate_output(
            content=output, tenant_id=tenant_id, user_id=user_id,
            agent_id=agent_id, session_id=session_id, policy_id=policy_id,
        )

        overall_passed = prompt_result.passed and output_result.passed

        return {
            "overall_passed": overall_passed,
            "prompt": prompt_result.to_dict(),
            "output": output_result.to_dict(),
            "blocked": (
                prompt_result.action == GuardAction.BLOCK.value
                or output_result.action == GuardAction.BLOCK.value
            ),
        }

    # ── Rule Evaluation ──────────────────────────────

    def _evaluate_rules(
        self, content: str, rules: List[GuardRule], direction: str
    ) -> Tuple[List[GuardViolation], int]:
        """Evaluate custom rules against content."""
        violations = []
        evaluated = 0

        # Sort by priority (descending)
        sorted_rules = sorted(rules, key=lambda r: r.priority, reverse=True)

        for rule in sorted_rules:
            if not rule.enabled:
                continue
            # Check direction match
            if rule.direction != direction and rule.direction != "both":
                continue

            evaluated += 1

            # Check keywords
            for keyword in rule.keywords:
                if keyword.lower() in content.lower():
                    violations.append(GuardViolation(
                        rule_id=rule.rule_id,
                        rule_name=rule.name,
                        category=rule.category,
                        severity=rule.severity,
                        direction=direction,
                        description=f"Keyword match: '{keyword}'",
                        matched_content=keyword,
                        matched_pattern=keyword,
                        position=content.lower().find(keyword.lower()),
                    ))

            # Check regex patterns
            import re
            for pattern in rule.patterns:
                try:
                    matches = list(re.finditer(pattern, content, re.IGNORECASE))
                    for match in matches:
                        violations.append(GuardViolation(
                            rule_id=rule.rule_id,
                            rule_name=rule.name,
                            category=rule.category,
                            severity=rule.severity,
                            direction=direction,
                            description=f"Pattern match: '{match.group()[:50]}'",
                            matched_content=match.group(),
                            matched_pattern=pattern,
                            position=match.start(),
                        ))
                except re.error:
                    pass  # Skip invalid patterns

        return violations, evaluated

    # ── Action Determination ─────────────────────────

    def _determine_action(self, violations: List[GuardViolation]) -> str:
        """Determine the appropriate action based on violations."""
        if not violations:
            return GuardAction.ALLOW.value

        highest = self._highest_severity(violations)

        # Auto-block for critical/high if configured
        if self._config.block_on_high_severity:
            if highest in (GuardSeverity.CRITICAL.value, GuardSeverity.HIGH.value):
                return GuardAction.BLOCK.value

        # Auto-allow for low if configured
        if self._config.allow_on_low_severity and highest == GuardSeverity.LOW.value:
            return GuardAction.ALLOW.value

        # Default action
        return self._config.default_action

    def _highest_severity(self, violations: List[GuardViolation]) -> str:
        """Get the highest severity from violations."""
        severity_order = {
            GuardSeverity.LOW.value: 0,
            GuardSeverity.MEDIUM.value: 1,
            GuardSeverity.HIGH.value: 2,
            GuardSeverity.CRITICAL.value: 3,
        }
        max_sev = GuardSeverity.LOW.value
        max_order = 0
        for v in violations:
            order = severity_order.get(v.severity, 0)
            if order > max_order:
                max_order = order
                max_sev = v.severity
        return max_sev

    # ── Audit Logging ────────────────────────────────

    def _log_audit(
        self,
        tenant_id: str, user_id: str, agent_id: str,
        session_id: str, direction: str, content: str,
        action: str, violations_count: int, highest_severity: str,
        policy_id: Optional[str] = None, latency_ms: float = 0.0,
    ):
        """Create an audit log entry."""
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

        entry = AuditLogEntry(
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            direction=direction,
            content_hash=content_hash,
            content_length=len(content),
            result_action=action,
            violations_count=violations_count,
            highest_severity=highest_severity,
            policy_id=policy_id or "",
            latenc_ms=latency_ms,
        )
        self._audit_logs.append(entry)

        # Trim old logs if exceeding retention
        max_logs = self._config.audit_log_retention_days * 1000
        if len(self._audit_logs) > max_logs:
            self._audit_logs = self._audit_logs[-max_logs:]

    # ── Stats ─────────────────────────────────────────

    def _update_stats(self, action: str):
        """Update internal statistics."""
        self._total_checks += 1
        if action == GuardAction.BLOCK.value:
            self._total_blocks += 1
        elif action == GuardAction.WARN.value:
            self._total_warns += 1
        elif action == GuardAction.ALLOW.value:
            self._total_allows += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            "total_checks": self._total_checks,
            "total_blocks": self._total_blocks,
            "total_warns": self._total_warns,
            "total_allows": self._total_allows,
            "total_redacts": self._total_checks - self._total_blocks - self._total_warns - self._total_allows,
            "audit_logs_count": len(self._audit_logs),
            "policies_count": len(self._policies),
            "block_rate": round(self._total_blocks / max(self._total_checks, 1), 4),
        }

    def get_audit_logs(
        self, limit: int = 100, tenant_id: Optional[str] = None,
    ) -> List[AuditLogEntry]:
        """Get recent audit logs, optionally filtered by tenant."""
        logs = self._audit_logs
        if tenant_id:
            logs = [l for l in logs if l.tenant_id == tenant_id]
        return logs[-limit:]

    def reset(self):
        """Reset engine state (for testing)."""
        self._policies.clear()
        self._audit_logs.clear()
        self._default_policy = None
        self._total_checks = 0
        self._total_blocks = 0
        self._total_warns = 0
        self._total_allows = 0

    # ── Helpers ──────────────────────────────────────

    def _get_policy(self, policy_id: Optional[str] = None) -> Optional[Policy]:
        """Get the policy to use for evaluation."""
        if policy_id:
            return self._policies.get(policy_id)
        return self._default_policy

    async def health_check(self) -> Dict[str, Any]:
        """Health check for the engine."""
        return {
            "status": "healthy",
            "enabled": self._config.enabled,
            "injection_detection": self._config.injection_detection,
            "output_filtering": self._config.output_filtering,
            "policies_loaded": len(self._policies),
            **self.get_stats(),
        }


# Singleton
_guardrail_engine: Optional[GuardrailEngine] = None


def get_guardrail_engine() -> GuardrailEngine:
    global _guardrail_engine
    if _guardrail_engine is None:
        _guardrail_engine = GuardrailEngine()
    return _guardrail_engine