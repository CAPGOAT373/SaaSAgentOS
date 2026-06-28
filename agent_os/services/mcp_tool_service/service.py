"""
Agent OS V6.0 - MCP Tool Service
Service layer wrapping the MCP Tool Registry, Sandbox, and Server
"""
import uuid
from typing import Optional, Dict, Any, List

from agent_os.core_platform.base import BaseService, ServiceContext
from agent_os.core_platform.exceptions import (
    NotFoundException, ValidationException, ToolNotFoundException,
    ToolExecutionException,
)
from agent_os.core_platform.mcp_tool_server.registry import (
    ToolRegistry, ToolDefinition, ToolResult, ToolParameter,
    ToolCategory, ToolStatus, get_tool_registry,
)
from agent_os.core_platform.mcp_tool_server.sandbox import (
    SandboxEngine, SandboxResult, get_sandbox_engine,
)
from agent_os.core_platform.mcp_tool_server.server import (
    MCPServer, get_mcp_server,
)
from agent_os.config import get_config


class MCPToolService(BaseService):
    """
    MCP Tool Service: tool registration, sandbox execution, plugin system.

    API:
    - register_tool / unregister_tool / get_tool / list_tools / update_tool
    - register_sandbox_tool: Register tool with sandbox code
    - invoke_tool / invoke_tool_by_name
    - search_tools / export_mcp_schema
    - get_stats / health_check
    """

    def __init__(self):
        super().__init__()
        self._registry = get_tool_registry()
        self._sandbox = get_sandbox_engine()
        self._server = get_mcp_server()
        self._config = get_config().mcp

    # ── Tool Registration ─────────────────────────────

    async def register_tool(
        self, tenant_id: str, name: str, description: str,
        parameters: Optional[List[Dict[str, Any]]] = None,
        category: str = ToolCategory.CUSTOM.value,
        tags: Optional[List[str]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Register a tool with a built-in handler wrapper."""
        params = []
        if parameters:
            for p in parameters:
                params.append(ToolParameter(
                    name=p.get("name", ""),
                    param_type=p.get("type", "string"),
                    description=p.get("description", ""),
                    required=p.get("required", False),
                    default_value=p.get("default"),
                    enum=p.get("enum"),
                    minimum=p.get("minimum"),
                    maximum=p.get("maximum"),
                    pattern=p.get("pattern"),
                ))

        async def handler(arguments: Dict[str, Any]) -> Any:
            return arguments

        tool = await self._registry.register_tool(
            tenant_id=tenant_id,
            name=name,
            description=description,
            handler=handler,
            parameters=params,
            category=category,
            tags=tags,
            output_schema=output_schema,
            metadata=metadata,
        )

        await self.emit_event("mcp.tool.registered", {
            "tool_id": tool.tool_id,
            "name": tool.name,
            "tenant_id": tenant_id,
        }, ctx)

        self.log("info", f"Registered tool: {name} (tenant: {tenant_id})", ctx)
        return tool.to_dict(include_schema=True)

    async def register_sandbox_tool(
        self, tenant_id: str, name: str, description: str,
        code: str, parameters: Optional[List[Dict[str, Any]]] = None,
        category: str = ToolCategory.CUSTOM.value,
        tags: Optional[List[str]] = None,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Register a tool with sandbox code for execution."""
        params = []
        if parameters:
            for p in parameters:
                params.append(ToolParameter(
                    name=p.get("name", ""),
                    param_type=p.get("type", "string"),
                    description=p.get("description", ""),
                    required=p.get("required", False),
                    default_value=p.get("default"),
                    enum=p.get("enum"),
                    minimum=p.get("minimum"),
                    maximum=p.get("maximum"),
                    pattern=p.get("pattern"),
                ))

        async def handler(arguments: Dict[str, Any]) -> Any:
            result = await self._sandbox.execute(code, arguments)
            if not result.success:
                raise ToolExecutionException(name, result.error)
            return result.result

        tool = await self._registry.register_tool(
            tenant_id=tenant_id,
            name=name,
            description=description,
            handler=handler,
            parameters=params,
            category=category,
            tags=tags,
        )

        await self.emit_event("mcp.tool.registered", {
            "tool_id": tool.tool_id,
            "name": tool.name,
            "tenant_id": tenant_id,
            "sandbox": True,
        }, ctx)

        self.log("info", f"Registered sandbox tool: {name} (tenant: {tenant_id})", ctx)
        return tool.to_dict(include_schema=True)

    async def unregister_tool(
        self, tool_id: str, ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Unregister a tool."""
        await self._registry.unregister_tool(tool_id)
        await self.emit_event("mcp.tool.unregistered", {
            "tool_id": tool_id,
        }, ctx)
        self.log("info", f"Unregistered tool: {tool_id}", ctx)
        return {"unregistered": True, "tool_id": tool_id}

    # ── Tool Discovery ────────────────────────────────

    async def get_tool(self, tool_id: str) -> Dict[str, Any]:
        """Get a tool by ID."""
        tool = await self._registry.get_tool(tool_id)
        return tool.to_dict(include_schema=True)

    async def get_tool_by_name(self, tenant_id: str, name: str) -> Optional[Dict[str, Any]]:
        """Get a tool by name within a tenant."""
        tool = await self._registry.get_tool_by_name(tenant_id, name)
        return tool.to_dict(include_schema=True) if tool else None

    async def list_tools(
        self, tenant_id: str, category: str = "",
        tags: Optional[List[str]] = None,
        status: str = "",
        limit: int = 100, offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List tools for a tenant."""
        tools = await self._registry.list_tools(
            tenant_id=tenant_id,
            category=category,
            tags=tags,
            status=status,
            limit=limit,
            offset=offset,
        )
        return [t.to_dict(include_schema=False) for t in tools]

    async def search_tools(
        self, tenant_id: str, query: str, limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search tools by name or description."""
        tools = await self._registry.search_tools(tenant_id, query, limit)
        return [t.to_dict(include_schema=False) for t in tools]

    # ── Tool Update ───────────────────────────────────

    async def update_tool(
        self, tool_id: str, description: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
        parameters: Optional[List[Dict[str, Any]]] = None,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Update tool metadata."""
        params = None
        if parameters is not None:
            params = []
            for p in parameters:
                params.append(ToolParameter(
                    name=p.get("name", ""),
                    param_type=p.get("type", "string"),
                    description=p.get("description", ""),
                    required=p.get("required", False),
                    default_value=p.get("default"),
                    enum=p.get("enum"),
                    minimum=p.get("minimum"),
                    maximum=p.get("maximum"),
                    pattern=p.get("pattern"),
                ))

        tool = await self._registry.update_tool(
            tool_id=tool_id,
            description=description,
            category=category,
            tags=tags,
            status=status,
            parameters=params,
        )

        await self.emit_event("mcp.tool.updated", {
            "tool_id": tool_id,
        }, ctx)

        return tool.to_dict(include_schema=True)

    # ── Tool Invocation ───────────────────────────────

    async def invoke_tool(
        self, tool_id: str, arguments: Dict[str, Any],
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Invoke a tool with validated arguments."""
        result = await self._registry.invoke_tool(tool_id, arguments)

        await self.emit_event("mcp.tool.executed", {
            "tool_id": tool_id,
            "tool_name": result.tool_name,
            "success": result.success,
            "duration_ms": result.duration_ms,
        }, ctx)

        self.log(
            "info" if result.success else "error",
            f"Tool {result.tool_name}: {'success' if result.success else 'failed'} ({result.duration_ms:.1f}ms)",
            ctx,
        )

        return result.to_dict()

    async def invoke_tool_by_name(
        self, tenant_id: str, name: str, arguments: Dict[str, Any],
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Invoke a tool by name within a tenant."""
        result = await self._registry.invoke_tool_by_name(tenant_id, name, arguments)

        await self.emit_event("mcp.tool.executed", {
            "tool_name": name,
            "tenant_id": tenant_id,
            "success": result.success,
            "duration_ms": result.duration_ms,
        }, ctx)

        return result.to_dict()

    # ── MCP Schema ────────────────────────────────────

    async def export_mcp_schema(self, tenant_id: str) -> Dict[str, Any]:
        """Export all active tools as MCP-compatible schema."""
        return await self._registry.export_mcp_schema(tenant_id)

    async def export_tool_schema(self, tool_id: str) -> Dict[str, Any]:
        """Export a single tool's MCP schema."""
        return await self._registry.export_tool_schema(tool_id)

    # ── MCP Protocol Methods ──────────────────────────

    async def tools_list(self, tenant_id: str) -> Dict[str, Any]:
        return await self._server.tools_list(tenant_id)

    async def tools_call(
        self, tenant_id: str, name: str, arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        return await self._server.tools_call(tenant_id, name, arguments)

    async def tools_get(self, tenant_id: str, name: str) -> Dict[str, Any]:
        return await self._server.tools_get(tenant_id, name)

    async def tools_search(
        self, tenant_id: str, query: str, limit: int = 20,
    ) -> Dict[str, Any]:
        return await self._server.tools_search(tenant_id, query, limit)

    # ── Statistics ────────────────────────────────────

    async def get_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get tool statistics for a tenant."""
        return await self._registry.get_stats(tenant_id)

    async def health_check(self) -> Dict[str, Any]:
        """Health check including all sub-components."""
        registry_hc = await self._registry.health_check()
        sandbox_hc = await self._sandbox.health_check()
        return {
            "status": "healthy",
            "service": "MCPToolService",
            "registry": registry_hc,
            "sandbox": sandbox_hc,
            "config": {
                "max_tools": self._config.max_tools,
                "sandbox_mode": self._config.sandbox_mode,
                "sandbox_timeout_ms": self._config.sandbox_timeout_ms,
                "server_port": self._config.server_port,
            },
        }


_mcp_tool_service: Optional[MCPToolService] = None


def get_mcp_tool_service() -> MCPToolService:
    global _mcp_tool_service
    if _mcp_tool_service is None:
        _mcp_tool_service = MCPToolService()
    return _mcp_tool_service