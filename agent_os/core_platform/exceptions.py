"""
Agent OS V6.0 - Base Exceptions
"""
from typing import Optional, Any, Dict


class AgentOSException(Exception):
    """Base exception for all Agent OS errors"""
    code: str = "AGENT_OS_ERROR"
    status_code: int = 500

    def __init__(self, message: str = "Internal server error", details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class NotFoundException(AgentOSException):
    code = "NOT_FOUND"
    status_code = 404

    def __init__(self, resource: str = "Resource", resource_id: str = ""):
        super().__init__(message=f"{resource} not found: {resource_id}", details={"resource": resource, "id": resource_id})


class ValidationException(AgentOSException):
    code = "VALIDATION_ERROR"
    status_code = 422


class AuthenticationException(AgentOSException):
    code = "AUTHENTICATION_ERROR"
    status_code = 401


class AuthorizationException(AgentOSException):
    code = "AUTHORIZATION_ERROR"
    status_code = 403


class ConflictException(AgentOSException):
    code = "CONFLICT"
    status_code = 409


class RateLimitException(AgentOSException):
    code = "RATE_LIMIT_EXCEEDED"
    status_code = 429


class BillingException(AgentOSException):
    code = "BILLING_ERROR"
    status_code = 402


class TenantNotFoundException(NotFoundException):
    def __init__(self, tenant_id: str):
        super().__init__(resource="Tenant", resource_id=tenant_id)


class AgentNotFoundException(NotFoundException):
    def __init__(self, agent_id: str):
        super().__init__(resource="Agent", resource_id=agent_id)


class PluginNotFoundException(NotFoundException):
    def __init__(self, plugin_id: str):
        super().__init__(resource="Plugin", resource_id=plugin_id)


class WorkflowNotFoundException(NotFoundException):
    def __init__(self, workflow_id: str):
        super().__init__(resource="Workflow", resource_id=workflow_id)


class InsufficientCreditsException(BillingException):
    def __init__(self, tenant_id: str, required: float, available: float):
        super().__init__(
            message=f"Insufficient credits for tenant {tenant_id}: need {required}, have {available}",
            details={"tenant_id": tenant_id, "required": required, "available": available},
        )


class ToolNotFoundException(NotFoundException):
    def __init__(self, tool_name: str):
        super().__init__(resource="Tool", resource_id=tool_name)


class ToolExecutionException(AgentOSException):
    code = "TOOL_EXECUTION_ERROR"
    status_code = 500

    def __init__(self, tool_name: str, error: str = ""):
        super().__init__(
            message=f"Tool '{tool_name}' execution failed: {error}",
            details={"tool_name": tool_name, "error": error},
        )


class SandboxException(AgentOSException):
    code = "SANDBOX_ERROR"
    status_code = 500

    def __init__(self, message: str = "Sandbox execution error", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, details=details)


class ToolSchemaValidationException(ValidationException):
    def __init__(self, tool_name: str, errors: list):
        super().__init__(
            message=f"Tool '{tool_name}' schema validation failed: {'; '.join(errors)}",
        )