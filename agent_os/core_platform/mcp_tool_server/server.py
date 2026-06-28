"""
Agent OS V6.0 - MCP Server
MCP protocol server: tool listing, tool execution, JSON-RPC endpoints
"""
import json
import uuid
from typing import Optional, Dict, Any, List

from agent_os.config import get_config
from agent_os.core_platform.mcp_tool_server.registry import (
    ToolRegistry, ToolDefinition, ToolResult, ToolParameter, ToolCategory,
    ToolStatus, get_tool_registry,
)
from agent_os.core_platform.mcp_tool_server.sandbox import (
    SandboxEngine, SandboxResult, get_sandbox_engine,
)
from agent_os.core_platform.exceptions import (
    ToolNotFoundException, ToolExecutionException, ValidationException,
)


class MCPServer:
    """
    MCP Protocol Server.

    Implements MCP JSON-RPC style endpoints:
    - tools/list: List all available tools with schemas
    - tools/call: Execute a tool with arguments
    - tools/get: Get a single tool's schema
    - tools/search: Search tools by name/description
    - tools/register: Register a new tool with sandbox code
    """

    def __init__(self):
        self._registry = get_tool_registry()
        self._sandbox = get_sandbox_engine()
        self._config = get_config().mcp
        self._server_id = str(uuid.uuid4())

    # ── MCP Protocol Methods ──────────────────────────

    async def tools_list(self, tenant_id: str) -> Dict[str, Any]:
        """MCP tools/list: List all available tools."""
        schema = await self._registry.export_mcp_schema(tenant_id)
        return {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "result": schema,
        }

    async def tools_call(
        self, tenant_id: str, name: str, arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """MCP tools/call: Execute a tool with arguments."""
        request_id = str(uuid.uuid4())

        tool = await self._registry.get_tool_by_name(tenant_id, name)
        if not tool:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32602,
                    "message": f"Tool not found: '{name}'",
                },
            }

        result = await self._registry.invoke_tool(tool.tool_id, arguments)

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result.to_dict(),
        }

    async def tools_get(self, tenant_id: str, name: str) -> Dict[str, Any]:
        """MCP-compatible: Get a single tool's schema."""
        tool = await self._registry.get_tool_by_name(tenant_id, name)
        if not tool:
            return {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "error": {
                    "code": -32602,
                    "message": f"Tool not found: '{name}'",
                },
            }

        return {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "result": tool.to_mcp_tool_schema(),
        }

    async def tools_search(
        self, tenant_id: str, query: str, limit: int = 20,
    ) -> Dict[str, Any]:
        """Search tools by name or description."""
        tools = await self._registry.search_tools(tenant_id, query, limit)
        return {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "result": {
                "tools": [t.to_mcp_tool_schema() for t in tools],
                "count": len(tools),
                "query": query,
            },
        }

    # ── Tool Registration with Sandbox Code ───────────

    async def register_sandbox_tool(
        self, tenant_id: str, name: str, description: str,
        code: str, parameters: Optional[List[Dict[str, Any]]] = None,
        category: str = ToolCategory.CUSTOM.value,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Register a tool with sandbox code.

        The code must define an async execute(input_data) function.
        """
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
            sandbox_result = await self._sandbox.execute(code, arguments)
            if not sandbox_result.success:
                raise ToolExecutionException(name, sandbox_result.error)
            return sandbox_result.result

        tool = await self._registry.register_tool(
            tenant_id=tenant_id,
            name=name,
            description=description,
            handler=handler,
            parameters=params,
            category=category,
            tags=tags,
        )

        return {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "result": tool.to_dict(include_schema=True),
        }

    # ── Direct Tool Registration ──────────────────────

    async def register_tool(
        self, tenant_id: str, name: str, description: str,
        handler, parameters: Optional[List[Dict[str, Any]]] = None,
        category: str = ToolCategory.CUSTOM.value,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Register a tool with a direct async handler function."""
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

        tool = await self._registry.register_tool(
            tenant_id=tenant_id,
            name=name,
            description=description,
            handler=handler,
            parameters=params,
            category=category,
            tags=tags,
        )

        return {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "result": tool.to_dict(include_schema=True),
        }

    # ── Tool Management ───────────────────────────────

    async def unregister_tool(self, tool_id: str) -> Dict[str, Any]:
        await self._registry.unregister_tool(tool_id)
        return {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "result": {"unregistered": True, "tool_id": tool_id},
        }

    async def get_tool(self, tool_id: str) -> Dict[str, Any]:
        tool = await self._registry.get_tool(tool_id)
        return {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "result": tool.to_dict(include_schema=True),
        }

    async def get_stats(self, tenant_id: str) -> Dict[str, Any]:
        stats = await self._registry.get_stats(tenant_id)
        return {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "result": stats,
        }

    # ── Health ────────────────────────────────────────

    async def health_check(self) -> Dict[str, Any]:
        registry_hc = await self._registry.health_check()
        sandbox_hc = await self._sandbox.health_check()
        return {
            "status": "healthy",
            "service": "MCPServer",
            "server_id": self._server_id,
            "registry": registry_hc,
            "sandbox": sandbox_hc,
            "config": {
                "port": self._config.server_port,
                "host": self._config.server_host,
                "sandbox_mode": self._config.sandbox_mode,
            },
        }


_mcp_server: Optional[MCPServer] = None


def get_mcp_server() -> MCPServer:
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = MCPServer()
    return _mcp_server