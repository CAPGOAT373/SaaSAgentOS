"""
Agent OS V6.0 - Guardrail Service
Service layer wrapping the guardrail policy engine
"""
from typing import Optional, Dict, Any, List

from agent_os.core_platform.base import BaseService, ServiceContext
from agent_os.core_platform.exceptions import NotFoundException, ValidationException
from agent_os.core_platform.guardrail.models import (
    GuardAction, GuardSeverity, GuardCategory, GuardDirection,
    GuardRule, GuardViolation, GuardResult, Policy, AuditLogEntry,
)
from agent_os.core_platform.guardrail.engine import GuardrailEngine, get_guardrail_engine
from agent_os.config import get_config


class GuardrailService(BaseService):
    """
    Guardrail Service: AI safety guardrails.

    API:
    - Prompt Validation: validate_prompt / validate_prompt_batch
    - Output Validation: validate_output / validate_output_batch
    - Full Cycle: validate_full_cycle
    - Policy Management: create_policy / get_policy / list_policies / update_policy / delete_policy
    - Rule Management: add_rule / remove_rule / update_rule
    - Audit: get_audit_logs / get_stats
    - Health: health_check
    """

    def __init__(self):
        super().__init__()
        self._engine = get_guardrail_engine()
        self._config = get_config().guardrail

    # ── Prompt Validation ────────────────────────────

    async def validate_prompt(
        self,
        content: str,
        tenant_id: str = "",
        user_id: str = "",
        agent_id: str = "",
        session_id: str = "",
        policy_id: Optional[str] = None,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Validate user prompt before sending to LLM."""
        result = await self._engine.validate_prompt(
            content=content,
            tenant_id=tenant_id or (ctx.tenant_id if ctx else ""),
            user_id=user_id or (ctx.user_id if ctx else ""),
            agent_id=agent_id or (ctx.agent_id if ctx else ""),
            session_id=session_id,
            policy_id=policy_id,
        )

        if result.action == GuardAction.BLOCK.value:
            await self.emit_event("guardrail.prompt.blocked", {
                "tenant_id": tenant_id,
                "violations_count": result.total_rules_triggered,
                "highest_severity": result.highest_severity,
            }, ctx)
            self.log("warn", f"Prompt blocked: {result.total_rules_triggered} violations", ctx)

        elif result.action == GuardAction.WARN.value:
            self.log("warn", f"Prompt warning: {result.total_rules_triggered} violations", ctx)

        return result.to_dict()

    async def validate_prompt_batch(
        self,
        contents: List[str],
        tenant_id: str = "",
        policy_id: Optional[str] = None,
        ctx: Optional[ServiceContext] = None,
    ) -> List[Dict[str, Any]]:
        """Validate multiple prompts in batch."""
        results = []
        for content in contents:
            result = await self._engine.validate_prompt(
                content=content, tenant_id=tenant_id, policy_id=policy_id,
            )
            results.append(result.to_dict())
        return results

    # ── Output Validation ────────────────────────────

    async def validate_output(
        self,
        content: str,
        tenant_id: str = "",
        user_id: str = "",
        agent_id: str = "",
        session_id: str = "",
        policy_id: Optional[str] = None,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Validate LLM output before returning to user."""
        result = await self._engine.validate_output(
            content=content,
            tenant_id=tenant_id or (ctx.tenant_id if ctx else ""),
            user_id=user_id or (ctx.user_id if ctx else ""),
            agent_id=agent_id or (ctx.agent_id if ctx else ""),
            session_id=session_id,
            policy_id=policy_id,
        )

        if result.action == GuardAction.BLOCK.value:
            await self.emit_event("guardrail.output.blocked", {
                "tenant_id": tenant_id,
                "violations_count": result.total_rules_triggered,
            }, ctx)
            self.log("warn", f"Output blocked: {result.total_rules_triggered} violations", ctx)

        elif result.action == GuardAction.REDACT.value:
            self.log("info", f"Output redacted: {result.total_rules_triggered} violations", ctx)

        return result.to_dict()

    # ── Full Cycle ───────────────────────────────────

    async def validate_full_cycle(
        self,
        prompt: str,
        output: str,
        tenant_id: str = "",
        user_id: str = "",
        agent_id: str = "",
        session_id: str = "",
        policy_id: Optional[str] = None,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Validate both prompt and output in a single call."""
        result = await self._engine.validate_full_cycle(
            prompt=prompt, output=output,
            tenant_id=tenant_id, user_id=user_id,
            agent_id=agent_id, session_id=session_id,
            policy_id=policy_id,
        )

        if result["blocked"]:
            await self.emit_event("guardrail.cycle.blocked", {
                "tenant_id": tenant_id,
            }, ctx)

        self.log("info", f"Full cycle validated: passed={result['overall_passed']}", ctx)
        return result

    # ── Policy Management ────────────────────────────

    async def create_policy(
        self,
        name: str,
        description: str = "",
        default_action: str = GuardAction.WARN.value,
        rules: Optional[List[Dict[str, Any]]] = None,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Create a new guardrail policy."""
        if not name:
            raise ValidationException("Policy name is required")

        guard_rules = []
        if rules:
            for r in rules:
                guard_rules.append(GuardRule(
                    name=r.get("name", ""),
                    description=r.get("description", ""),
                    category=r.get("category", GuardCategory.CUSTOM.value),
                    direction=r.get("direction", GuardDirection.INPUT.value),
                    patterns=r.get("patterns", []),
                    keywords=r.get("keywords", []),
                    action=r.get("action", GuardAction.WARN.value),
                    severity=r.get("severity", GuardSeverity.MEDIUM.value),
                    enabled=r.get("enabled", True),
                    priority=r.get("priority", 0),
                ))

        policy = Policy(
            name=name,
            description=description,
            rules=guard_rules,
            default_action=default_action,
        )
        self._engine.add_policy(policy)

        await self.emit_event("guardrail.policy.created", {
            "policy_id": policy.policy_id,
            "name": name,
        }, ctx)

        self.log("info", f"Policy created: {policy.policy_id}", ctx)
        return policy.to_dict()

    async def get_policy(self, policy_id: str) -> Dict[str, Any]:
        """Get a policy by ID."""
        policy = self._engine.get_policy(policy_id)
        if not policy:
            raise NotFoundException("Policy", policy_id)
        return policy.to_dict()

    async def list_policies(
        self, ctx: Optional[ServiceContext] = None,
    ) -> List[Dict[str, Any]]:
        """List all policies."""
        return [p.to_dict() for p in self._engine.list_policies()]

    async def update_policy(
        self,
        policy_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        default_action: Optional[str] = None,
        enabled: Optional[bool] = None,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Update an existing policy."""
        policy = self._engine.get_policy(policy_id)
        if not policy:
            raise NotFoundException("Policy", policy_id)

        if name is not None:
            policy.name = name
        if description is not None:
            policy.description = description
        if default_action is not None:
            policy.default_action = default_action
        if enabled is not None:
            policy.enabled = enabled

        from datetime import datetime, timezone
        policy.updated_at = datetime.now(timezone.utc).isoformat()

        self.log("info", f"Policy updated: {policy_id}", ctx)
        return policy.to_dict()

    async def delete_policy(
        self, policy_id: str, ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Delete a policy."""
        if not self._engine.delete_policy(policy_id):
            raise NotFoundException("Policy", policy_id)

        await self.emit_event("guardrail.policy.deleted", {
            "policy_id": policy_id,
        }, ctx)

        self.log("info", f"Policy deleted: {policy_id}", ctx)
        return {"deleted": True, "policy_id": policy_id}

    # ── Rule Management ──────────────────────────────

    async def add_rule(
        self,
        policy_id: str,
        name: str,
        category: str = GuardCategory.CUSTOM.value,
        direction: str = GuardDirection.INPUT.value,
        patterns: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        action: str = GuardAction.WARN.value,
        severity: str = GuardSeverity.MEDIUM.value,
        priority: int = 0,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Add a rule to an existing policy."""
        policy = self._engine.get_policy(policy_id)
        if not policy:
            raise NotFoundException("Policy", policy_id)

        rule = GuardRule(
            name=name,
            category=category,
            direction=direction,
            patterns=patterns or [],
            keywords=keywords or [],
            action=action,
            severity=severity,
            priority=priority,
        )
        policy.rules.append(rule)

        self.log("info", f"Rule added to policy {policy_id}: {rule.rule_id}", ctx)
        return rule.to_dict()

    async def remove_rule(
        self, policy_id: str, rule_id: str,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Remove a rule from a policy."""
        policy = self._engine.get_policy(policy_id)
        if not policy:
            raise NotFoundException("Policy", policy_id)

        policy.rules = [r for r in policy.rules if r.rule_id != rule_id]

        self.log("info", f"Rule removed from policy {policy_id}: {rule_id}", ctx)
        return {"removed": True, "policy_id": policy_id, "rule_id": rule_id}

    # ── Audit & Stats ────────────────────────────────

    async def get_audit_logs(
        self, limit: int = 100, tenant_id: Optional[str] = None,
        ctx: Optional[ServiceContext] = None,
    ) -> List[Dict[str, Any]]:
        """Get audit logs."""
        logs = self._engine.get_audit_logs(limit=limit, tenant_id=tenant_id)
        return [log.to_dict() for log in logs]

    async def get_stats(
        self, ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Get guardrail statistics."""
        return self._engine.get_stats()

    async def reset(self, ctx: Optional[ServiceContext] = None):
        """Reset engine state (for testing)."""
        self._engine.reset()
        self.log("info", "Guardrail engine reset", ctx)

    # ── Health Check ─────────────────────────────────

    async def health_check(self) -> Dict[str, Any]:
        """Health check for guardrail service."""
        engine_health = await self._engine.health_check()
        return {
            "status": "healthy",
            "service": "GuardrailService",
            "engine": engine_health,
        }


# Singleton
_guardrail_service: Optional[GuardrailService] = None


def get_guardrail_service() -> GuardrailService:
    global _guardrail_service
    if _guardrail_service is None:
        _guardrail_service = GuardrailService()
    return _guardrail_service