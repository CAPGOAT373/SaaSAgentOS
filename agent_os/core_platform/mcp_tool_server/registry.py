"""
Agent OS V6.0 - MCP Tool Registry
Tool registration, discovery, schema validation, invocation
"""
import re
import uuid
import inspect
from enum import Enum
from typing import Optional, Dict, Any, List, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from agent_os.config import get_config
from agent_os.core_platform.exceptions import (
    NotFoundException, ValidationException, ToolNotFoundException,
    ToolSchemaValidationException, ToolExecutionException,
    ConflictException,
)


class ToolCategory(str, Enum):
    FILE = "file"
    NETWORK = "network"
    DATABASE = "database"
    COMPUTE = "compute"
    AI = "ai"
    SYSTEM = "system"
    CUSTOM = "custom"


class ToolStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"


@dataclass
class ToolParameter:
    """JSON Schema parameter definition for a tool."""
    name: str
    param_type: str = "string"  # string | number | integer | boolean | array | object
    description: str = ""
    required: bool = False
    default_value: Any = None
    enum: Optional[List[Any]] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    pattern: Optional[str] = None  # regex pattern for string validation

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "type": self.param_type,
            "description": self.description,
            "required": self.required,
        }
        if self.default_value is not None:
            d["default"] = self.default_value
        if self.enum is not None:
            d["enum"] = self.enum
        if self.minimum is not None:
            d["minimum"] = self.minimum
        if self.maximum is not None:
            d["maximum"] = self.maximum
        if self.pattern is not None:
            d["pattern"] = self.pattern
        return d

    def to_json_schema(self) -> dict:
        """Convert to JSON Schema property definition."""
        schema: Dict[str, Any] = {"type": self.param_type}
        if self.description:
            schema["description"] = self.description
        if self.default_value is not None:
            schema["default"] = self.default_value
        if self.enum is not None:
            schema["enum"] = self.enum
        if self.minimum is not None:
            schema["minimum"] = self.minimum
        if self.maximum is not None:
            schema["maximum"] = self.maximum
        if self.pattern is not None:
            schema["pattern"] = self.pattern
        return schema


@dataclass
class ToolDefinition:
    """Complete tool definition with schema and handler."""
    tool_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    description: str = ""
    category: str = ToolCategory.CUSTOM.value
    status: str = ToolStatus.ACTIVE.value
    parameters: List[ToolParameter] = field(default_factory=list)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Runtime handler (not serialized)
    handler: Optional[Callable[..., Awaitable[Any]]] = field(default=None, repr=False, compare=False)

    def to_dict(self, include_schema: bool = True) -> dict:
        d = {
            "tool_id": self.tool_id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "status": self.status,
            "tags": self.tags,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }
        if include_schema:
            d["parameters"] = [p.to_dict() for p in self.parameters]
            d["output_schema"] = self.output_schema
        return d

    def to_mcp_tool_schema(self) -> dict:
        """Convert to MCP-compatible tool schema."""
        properties = {}
        required_params = []
        for p in self.parameters:
            properties[p.name] = p.to_json_schema()
            if p.required:
                required_params.append(p.name)

        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": properties,
                "required": required_params,
            },
        }

    def get_required_params(self) -> List[str]:
        return [p.name for p in self.parameters if p.required]


@dataclass
class ToolResult:
    """Result of a tool execution."""
    tool_id: str = ""
    tool_name: str = ""
    success: bool = True
    result: Any = None
    error: str = ""
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "tool_id": self.tool_id,
            "tool_name": self.tool_name,
            "success": self.success,
            "duration_ms": round(self.duration_ms, 2),
        }
        if self.success:
            d["result"] = self.result
        else:
            d["error"] = self.error
        if self.metadata:
            d["metadata"] = self.metadata
        return d


class ToolRegistry:
    """
    MCP Tool Registry: register, discover, validate, and invoke tools.

    Features:
    - Tenant-scoped tool registration
    - JSON Schema parameter validation
    - Tool discovery by name, category, tags
    - Handler invocation with input validation
    - Tool lifecycle management (activate/deactivate/deprecate)
    """

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}  # tool_id → ToolDefinition
        self._config = get_config().mcp

    # ── Tool Registration ─────────────────────────────

    async def register_tool(
        self, tenant_id: str, name: str, description: str,
        handler: Callable[..., Awaitable[Any]],
        parameters: Optional[List[ToolParameter]] = None,
        category: str = ToolCategory.CUSTOM.value,
        tags: Optional[List[str]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ToolDefinition:
        """Register a new tool with handler."""
        # Validate name
        if not name or not name.strip():
            raise ValidationException("Tool name cannot be empty")
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_-]*$', name):
            raise ValidationException(
                f"Invalid tool name '{name}': must match [a-zA-Z_][a-zA-Z0-9_-]*"
            )
        if len(name) > self._config.max_tool_name_length:
            raise ValidationException(
                f"Tool name too long: {len(name)} > {self._config.max_tool_name_length}"
            )

        # Check duplicate name within tenant
        for t in self._tools.values():
            if t.tenant_id == tenant_id and t.name == name:
                raise ConflictException(
                    f"Tool '{name}' already registered in tenant {tenant_id}"
                )

        # Check max tools limit
        tenant_tools = [t for t in self._tools.values() if t.tenant_id == tenant_id]
        if len(tenant_tools) >= self._config.max_tools:
            raise ValidationException(
                f"Maximum tools ({self._config.max_tools}) reached for tenant {tenant_id}"
            )

        # Validate parameters
        if parameters:
            self._validate_parameters(parameters)

        tool = ToolDefinition(
            tenant_id=tenant_id,
            name=name,
            description=description or "",
            category=category,
            parameters=parameters or [],
            output_schema=output_schema or {},
            tags=tags or [],
            handler=handler,
            metadata=metadata or {},
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

        self._tools[tool.tool_id] = tool
        return tool

    async def unregister_tool(self, tool_id: str) -> bool:
        """Unregister a tool."""
        if tool_id not in self._tools:
            raise ToolNotFoundException(tool_id)
        del self._tools[tool_id]
        return True

    async def get_tool(self, tool_id: str) -> ToolDefinition:
        """Get a tool by ID."""
        tool = self._tools.get(tool_id)
        if not tool:
            raise ToolNotFoundException(tool_id)
        return tool

    async def get_tool_by_name(self, tenant_id: str, name: str) -> Optional[ToolDefinition]:
        """Get a tool by name within a tenant."""
        for t in self._tools.values():
            if t.tenant_id == tenant_id and t.name == name:
                return t
        return None

    async def list_tools(
        self, tenant_id: str, category: str = "",
        tags: Optional[List[str]] = None,
        status: str = "",
        limit: int = 100, offset: int = 0,
    ) -> List[ToolDefinition]:
        """List tools for a tenant with optional filtering."""
        results = [
            t for t in self._tools.values()
            if t.tenant_id == tenant_id
        ]

        if category:
            results = [t for t in results if t.category == category]
        if tags:
            results = [t for t in results if any(tag in t.tags for tag in tags)]
        if status:
            results = [t for t in results if t.status == status]

        results.sort(key=lambda t: t.updated_at or t.created_at, reverse=True)
        return results[offset:offset + limit]

    async def update_tool(
        self, tool_id: str, description: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
        parameters: Optional[List[ToolParameter]] = None,
        handler: Optional[Callable[..., Awaitable[Any]]] = None,
    ) -> ToolDefinition:
        """Update tool metadata and handler."""
        tool = await self.get_tool(tool_id)

        if description is not None:
            tool.description = description
        if category is not None:
            tool.category = category
        if tags is not None:
            tool.tags = tags
        if status is not None:
            tool.status = status
        if parameters is not None:
            self._validate_parameters(parameters)
            tool.parameters = parameters
        if handler is not None:
            tool.handler = handler

        tool.updated_at = datetime.now(timezone.utc).isoformat()
        return tool

    # ── Tool Invocation ───────────────────────────────

    async def invoke_tool(
        self, tool_id: str, arguments: Dict[str, Any],
    ) -> ToolResult:
        """Invoke a tool with validated arguments."""
        import time
        start = time.time()

        tool = await self.get_tool(tool_id)

        if tool.status != ToolStatus.ACTIVE.value:
            raise ValidationException(f"Tool '{tool.name}' is not active (status: {tool.status})")

        if not tool.handler:
            raise ToolExecutionException(tool.name, "No handler registered")

        # Validate input parameters
        self._validate_arguments(tool, arguments)

        # Apply default values
        for p in tool.parameters:
            if p.name not in arguments and p.default_value is not None:
                arguments[p.name] = p.default_value

        try:
            result = tool.handler(arguments)
            if inspect.iscoroutine(result) or inspect.isawaitable(result):
                result = await result
            duration_ms = (time.time() - start) * 1000
            return ToolResult(
                tool_id=tool_id,
                tool_name=tool.name,
                success=True,
                result=result,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            return ToolResult(
                tool_id=tool_id,
                tool_name=tool.name,
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )

    async def invoke_tool_by_name(
        self, tenant_id: str, name: str, arguments: Dict[str, Any],
    ) -> ToolResult:
        """Invoke a tool by name within a tenant."""
        tool = await self.get_tool_by_name(tenant_id, name)
        if not tool:
            raise ToolNotFoundException(name)
        return await self.invoke_tool(tool.tool_id, arguments)

    # ── Validation ────────────────────────────────────

    def _validate_parameters(self, parameters: List[ToolParameter]):
        """Validate parameter definitions."""
        names = set()
        valid_types = {"string", "number", "integer", "boolean", "array", "object"}

        for p in parameters:
            if not p.name or not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', p.name):
                raise ValidationException(f"Invalid parameter name: '{p.name}'")
            if p.param_type not in valid_types:
                raise ValidationException(f"Invalid parameter type '{p.param_type}' for '{p.name}'")
            if p.name in names:
                raise ValidationException(f"Duplicate parameter name: '{p.name}'")
            names.add(p.name)

    def _validate_arguments(self, tool: ToolDefinition, arguments: Dict[str, Any]):
        """Validate arguments against tool parameter schema."""
        errors = []

        for p in tool.parameters:
            val = arguments.get(p.name)

            # Check required
            if p.required and val is None and p.default_value is None:
                errors.append(f"Missing required parameter: '{p.name}'")
                continue

            if val is None:
                continue

            # Type validation
            expected = p.param_type
            if expected == "string" and not isinstance(val, str):
                errors.append(f"Parameter '{p.name}' expected string, got {type(val).__name__}")
            elif expected == "number" and not isinstance(val, (int, float)):
                errors.append(f"Parameter '{p.name}' expected number, got {type(val).__name__}")
            elif expected == "integer" and not isinstance(val, int):
                errors.append(f"Parameter '{p.name}' expected integer, got {type(val).__name__}")
            elif expected == "boolean" and not isinstance(val, bool):
                errors.append(f"Parameter '{p.name}' expected boolean, got {type(val).__name__}")
            elif expected == "array" and not isinstance(val, list):
                errors.append(f"Parameter '{p.name}' expected array, got {type(val).__name__}")
            elif expected == "object" and not isinstance(val, dict):
                errors.append(f"Parameter '{p.name}' expected object, got {type(val).__name__}")

            # Enum validation
            if p.enum is not None and val not in p.enum:
                errors.append(f"Parameter '{p.name}' value '{val}' not in enum: {p.enum}")

            # Range validation
            if isinstance(val, (int, float)):
                if p.minimum is not None and val < p.minimum:
                    errors.append(f"Parameter '{p.name}' value {val} < minimum {p.minimum}")
                if p.maximum is not None and val > p.maximum:
                    errors.append(f"Parameter '{p.name}' value {val} > maximum {p.maximum}")

            # Pattern validation
            if p.pattern and isinstance(val, str):
                if not re.match(p.pattern, val):
                    errors.append(f"Parameter '{p.name}' value '{val}' does not match pattern '{p.pattern}'")

        if errors:
            raise ToolSchemaValidationException(tool.name, errors)

    # ── Schema Export ─────────────────────────────────

    async def export_mcp_schema(self, tenant_id: str) -> Dict[str, Any]:
        """Export all tools as MCP-compatible schema."""
        tools = [t for t in self._tools.values() if t.tenant_id == tenant_id and t.status == ToolStatus.ACTIVE.value]
        return {
            "tools": [t.to_mcp_tool_schema() for t in tools],
            "count": len(tools),
        }

    async def export_tool_schema(self, tool_id: str) -> dict:
        """Export a single tool's MCP schema."""
        tool = await self.get_tool(tool_id)
        return tool.to_mcp_tool_schema()

    # ── Statistics ────────────────────────────────────

    async def get_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get tool statistics for a tenant."""
        tools = [t for t in self._tools.values() if t.tenant_id == tenant_id]

        categories = {}
        for t in tools:
            cat = t.category or "uncategorized"
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "tenant_id": tenant_id,
            "total_tools": len(tools),
            "active_tools": sum(1 for t in tools if t.status == ToolStatus.ACTIVE.value),
            "inactive_tools": sum(1 for t in tools if t.status == ToolStatus.INACTIVE.value),
            "deprecated_tools": sum(1 for t in tools if t.status == ToolStatus.DEPRECATED.value),
            "categories": categories,
            "config": {
                "max_tools": self._config.max_tools,
                "sandbox_mode": self._config.sandbox_mode,
            },
        }

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "service": "ToolRegistry",
            "total_tools": len(self._tools),
        }

    # ── Search ────────────────────────────────────────

    async def search_tools(
        self, tenant_id: str, query: str, limit: int = 20,
    ) -> List[ToolDefinition]:
        """Search tools by name or description."""
        query_lower = query.lower()
        results = []
        for t in self._tools.values():
            if t.tenant_id != tenant_id:
                continue
            if query_lower in t.name.lower() or query_lower in t.description.lower():
                results.append(t)
        results.sort(key=lambda t: t.updated_at or t.created_at, reverse=True)
        return results[:limit]


_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry