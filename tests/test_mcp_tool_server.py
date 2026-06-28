"""
Agent OS V6.0 - MCP Tool Server Tests
Unit tests for ToolRegistry, SandboxEngine, MCPServer, and MCPToolService
"""
import pytest
import asyncio

from agent_os.config import get_config, MCPConfig
from agent_os.core_platform.exceptions import (
    ValidationException, ConflictException, NotFoundException,
    ToolNotFoundException, ToolExecutionException,
    SandboxException, ToolSchemaValidationException,
)
from agent_os.core_platform.mcp_tool_server.registry import (
    ToolRegistry, ToolDefinition, ToolResult, ToolParameter,
    ToolCategory, ToolStatus, get_tool_registry,
)
from agent_os.core_platform.mcp_tool_server.sandbox import (
    SandboxEngine, SandboxResult, SandboxMode, get_sandbox_engine,
)
from agent_os.core_platform.mcp_tool_server.server import (
    MCPServer, get_mcp_server,
)
from agent_os.services.mcp_tool_service.service import (
    MCPToolService, get_mcp_tool_service,
)


# ============================================================
# ToolParameter Tests
# ============================================================

class TestToolParameter:
    """Tests for ToolParameter model."""

    def test_basic_parameter(self):
        p = ToolParameter(name="text", param_type="string", required=True)
        assert p.name == "text"
        assert p.param_type == "string"
        assert p.required is True

    def test_to_dict_basic(self):
        p = ToolParameter(name="count", param_type="integer")
        d = p.to_dict()
        assert d["name"] == "count"
        assert d["type"] == "integer"
        assert d["required"] is False

    def test_to_dict_with_constraints(self):
        p = ToolParameter(
            name="age", param_type="integer",
            minimum=0, maximum=150, default_value=18,
            description="User age",
        )
        d = p.to_dict()
        assert d["minimum"] == 0
        assert d["maximum"] == 150
        assert d["default"] == 18
        assert d["description"] == "User age"

    def test_to_dict_with_enum(self):
        p = ToolParameter(
            name="status", param_type="string",
            enum=["active", "inactive", "pending"],
        )
        d = p.to_dict()
        assert d["enum"] == ["active", "inactive", "pending"]

    def test_to_dict_with_pattern(self):
        p = ToolParameter(
            name="email", param_type="string",
            pattern=r"^[a-z]+@[a-z]+\.com$",
        )
        d = p.to_dict()
        assert d["pattern"] == r"^[a-z]+@[a-z]+\.com$"

    def test_to_json_schema(self):
        p = ToolParameter(
            name="text", param_type="string",
            description="Input text", required=True,
        )
        schema = p.to_json_schema()
        assert schema["type"] == "string"
        assert schema["description"] == "Input text"

    def test_to_json_schema_with_enum(self):
        p = ToolParameter(name="role", param_type="string", enum=["admin", "user"])
        schema = p.to_json_schema()
        assert schema["enum"] == ["admin", "user"]

    def test_to_json_schema_with_default(self):
        p = ToolParameter(name="limit", param_type="integer", default_value=10)
        schema = p.to_json_schema()
        assert schema["default"] == 10


# ============================================================
# ToolDefinition Tests
# ============================================================

class TestToolDefinition:
    """Tests for ToolDefinition model."""

    def test_create_definition(self):
        t = ToolDefinition(tenant_id="t1", name="echo", description="Echo tool")
        assert t.tool_id is not None
        assert t.name == "echo"
        assert t.status == ToolStatus.ACTIVE.value

    def test_to_dict_basic(self):
        t = ToolDefinition(tenant_id="t1", name="calc", description="Calculator")
        d = t.to_dict(include_schema=False)
        assert d["name"] == "calc"
        assert "parameters" not in d

    def test_to_dict_with_schema(self):
        t = ToolDefinition(
            tenant_id="t1", name="calc",
            parameters=[ToolParameter(name="x", param_type="integer")],
        )
        d = t.to_dict(include_schema=True)
        assert "parameters" in d
        assert len(d["parameters"]) == 1

    def test_to_mcp_tool_schema(self):
        t = ToolDefinition(
            tenant_id="t1", name="greet",
            description="Say hello",
            parameters=[
                ToolParameter(name="name", param_type="string", required=True),
                ToolParameter(name="age", param_type="integer"),
            ],
        )
        schema = t.to_mcp_tool_schema()
        assert schema["name"] == "greet"
        assert schema["description"] == "Say hello"
        assert "inputSchema" in schema
        assert "name" in schema["inputSchema"]["properties"]
        assert "age" in schema["inputSchema"]["properties"]
        assert schema["inputSchema"]["required"] == ["name"]

    def test_get_required_params(self):
        t = ToolDefinition(
            tenant_id="t1", name="test",
            parameters=[
                ToolParameter(name="a", required=True),
                ToolParameter(name="b", required=False),
                ToolParameter(name="c", required=True),
            ],
        )
        assert t.get_required_params() == ["a", "c"]

    def test_get_required_params_none(self):
        t = ToolDefinition(tenant_id="t1", name="test")
        assert t.get_required_params() == []


# ============================================================
# ToolResult Tests
# ============================================================

class TestToolResult:
    """Tests for ToolResult model."""

    def test_success_result(self):
        r = ToolResult(
            tool_id="t1", tool_name="echo",
            success=True, result="hello", duration_ms=5.5,
        )
        d = r.to_dict()
        assert d["success"] is True
        assert d["result"] == "hello"
        assert d["duration_ms"] == 5.5
        assert "error" not in d

    def test_failure_result(self):
        r = ToolResult(
            tool_id="t1", tool_name="calc",
            success=False, error="division by zero", duration_ms=1.0,
        )
        d = r.to_dict()
        assert d["success"] is False
        assert d["error"] == "division by zero"
        assert "result" not in d

    def test_result_with_metadata(self):
        r = ToolResult(
            tool_id="t1", tool_name="test",
            success=True, result="ok", metadata={"version": "1.0"},
        )
        d = r.to_dict()
        assert d["metadata"]["version"] == "1.0"


# ============================================================
# ToolCategory / ToolStatus Tests
# ============================================================

class TestToolEnums:
    """Tests for ToolCategory and ToolStatus enums."""

    def test_categories(self):
        assert ToolCategory.FILE.value == "file"
        assert ToolCategory.NETWORK.value == "network"
        assert ToolCategory.DATABASE.value == "database"
        assert ToolCategory.COMPUTE.value == "compute"
        assert ToolCategory.AI.value == "ai"
        assert ToolCategory.SYSTEM.value == "system"
        assert ToolCategory.CUSTOM.value == "custom"

    def test_statuses(self):
        assert ToolStatus.ACTIVE.value == "active"
        assert ToolStatus.INACTIVE.value == "inactive"
        assert ToolStatus.DEPRECATED.value == "deprecated"


# ============================================================
# ToolRegistry Tests
# ============================================================

class TestToolRegistry:
    """Tests for ToolRegistry - registration, validation, invocation."""

    @pytest.fixture
    def registry(self):
        reg = ToolRegistry()
        reg._tools.clear()
        return reg

    async def _echo_handler(self, args):
        return f"Echo: {args.get('text', '')}"

    # ── Registration ──────────────────────────────────

    @pytest.mark.asyncio
    async def test_register_tool(self, registry):
        tool = await registry.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", handler=self._echo_handler,
        )
        assert tool.name == "echo"
        assert tool.tenant_id == "t1"

    @pytest.mark.asyncio
    async def test_register_empty_name(self, registry):
        with pytest.raises(ValidationException):
            await registry.register_tool(
                tenant_id="t1", name="", description="bad",
                handler=self._echo_handler,
            )

    @pytest.mark.asyncio
    async def test_register_invalid_name(self, registry):
        with pytest.raises(ValidationException):
            await registry.register_tool(
                tenant_id="t1", name="123bad",
                description="bad", handler=self._echo_handler,
            )

    @pytest.mark.asyncio
    async def test_register_name_too_long(self, registry):
        with pytest.raises(ValidationException):
            await registry.register_tool(
                tenant_id="t1", name="a" * 200,
                description="bad", handler=self._echo_handler,
            )

    @pytest.mark.asyncio
    async def test_register_duplicate_name(self, registry):
        await registry.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", handler=self._echo_handler,
        )
        with pytest.raises(ConflictException):
            await registry.register_tool(
                tenant_id="t1", name="echo",
                description="Dup", handler=self._echo_handler,
            )

    @pytest.mark.asyncio
    async def test_register_duplicate_name_different_tenant(self, registry):
        await registry.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", handler=self._echo_handler,
        )
        tool = await registry.register_tool(
            tenant_id="t2", name="echo",
            description="Echo2", handler=self._echo_handler,
        )
        assert tool.tenant_id == "t2"

    @pytest.mark.asyncio
    async def test_register_with_parameters(self, registry):
        tool = await registry.register_tool(
            tenant_id="t1", name="calc",
            description="Calculator", handler=self._echo_handler,
            parameters=[
                ToolParameter(name="x", param_type="integer", required=True),
                ToolParameter(name="y", param_type="integer", default_value=0),
            ],
        )
        assert len(tool.parameters) == 2

    @pytest.mark.asyncio
    async def test_register_with_tags(self, registry):
        tool = await registry.register_tool(
            tenant_id="t1", name="util",
            description="Utility", handler=self._echo_handler,
            tags=["util", "helper"],
        )
        assert "util" in tool.tags
        assert "helper" in tool.tags

    @pytest.mark.asyncio
    async def test_register_invalid_parameter_name(self, registry):
        with pytest.raises(ValidationException):
            await registry.register_tool(
                tenant_id="t1", name="test",
                description="test", handler=self._echo_handler,
                parameters=[ToolParameter(name="123bad", param_type="string")],
            )

    @pytest.mark.asyncio
    async def test_register_invalid_parameter_type(self, registry):
        with pytest.raises(ValidationException):
            await registry.register_tool(
                tenant_id="t1", name="test",
                description="test", handler=self._echo_handler,
                parameters=[ToolParameter(name="x", param_type="invalid")],
            )

    @pytest.mark.asyncio
    async def test_register_duplicate_parameter_name(self, registry):
        with pytest.raises(ValidationException):
            await registry.register_tool(
                tenant_id="t1", name="test",
                description="test", handler=self._echo_handler,
                parameters=[
                    ToolParameter(name="x", param_type="string"),
                    ToolParameter(name="x", param_type="integer"),
                ],
            )

    @pytest.mark.asyncio
    async def test_register_max_tools_limit(self, registry):
        cfg = get_config().mcp
        for i in range(cfg.max_tools):
            await registry.register_tool(
                tenant_id="t1", name=f"tool_{i}",
                description="filler", handler=self._echo_handler,
            )
        with pytest.raises(ValidationException):
            await registry.register_tool(
                tenant_id="t1", name="one_more",
                description="overflow", handler=self._echo_handler,
            )

    # ── Get Tool ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_tool(self, registry):
        tool = await registry.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", handler=self._echo_handler,
        )
        fetched = await registry.get_tool(tool.tool_id)
        assert fetched.name == "echo"

    @pytest.mark.asyncio
    async def test_get_tool_not_found(self, registry):
        with pytest.raises(ToolNotFoundException):
            await registry.get_tool("nonexistent")

    @pytest.mark.asyncio
    async def test_get_tool_by_name(self, registry):
        await registry.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", handler=self._echo_handler,
        )
        tool = await registry.get_tool_by_name("t1", "echo")
        assert tool is not None

    @pytest.mark.asyncio
    async def test_get_tool_by_name_not_found(self, registry):
        tool = await registry.get_tool_by_name("t1", "nonexistent")
        assert tool is None

    # ── List Tools ────────────────────────────────────

    @pytest.mark.asyncio
    async def test_list_tools(self, registry):
        await registry.register_tool(
            tenant_id="t1", name="a", description="a", handler=self._echo_handler,
        )
        await registry.register_tool(
            tenant_id="t1", name="b", description="b", handler=self._echo_handler,
        )
        tools = await registry.list_tools("t1")
        assert len(tools) == 2

    @pytest.mark.asyncio
    async def test_list_tools_category_filter(self, registry):
        await registry.register_tool(
            tenant_id="t1", name="sys", description="sys",
            handler=self._echo_handler, category=ToolCategory.SYSTEM.value,
        )
        await registry.register_tool(
            tenant_id="t1", name="usr", description="usr",
            handler=self._echo_handler, category=ToolCategory.CUSTOM.value,
        )
        tools = await registry.list_tools("t1", category=ToolCategory.SYSTEM.value)
        assert len(tools) == 1
        assert tools[0].name == "sys"

    @pytest.mark.asyncio
    async def test_list_tools_tag_filter(self, registry):
        await registry.register_tool(
            tenant_id="t1", name="a", description="a",
            handler=self._echo_handler, tags=["tag1"],
        )
        await registry.register_tool(
            tenant_id="t1", name="b", description="b",
            handler=self._echo_handler, tags=["tag2"],
        )
        tools = await registry.list_tools("t1", tags=["tag1"])
        assert len(tools) == 1

    @pytest.mark.asyncio
    async def test_list_tools_status_filter(self, registry):
        tool = await registry.register_tool(
            tenant_id="t1", name="a", description="a", handler=self._echo_handler,
        )
        await registry.update_tool(tool.tool_id, status=ToolStatus.INACTIVE.value)
        active = await registry.list_tools("t1", status=ToolStatus.ACTIVE.value)
        assert len(active) == 0

    @pytest.mark.asyncio
    async def test_list_tools_tenant_isolation(self, registry):
        await registry.register_tool(
            tenant_id="t1", name="a", description="a", handler=self._echo_handler,
        )
        await registry.register_tool(
            tenant_id="t2", name="b", description="b", handler=self._echo_handler,
        )
        assert len(await registry.list_tools("t1")) == 1
        assert len(await registry.list_tools("t2")) == 1

    @pytest.mark.asyncio
    async def test_list_tools_pagination(self, registry):
        for i in range(10):
            await registry.register_tool(
                tenant_id="t1", name=f"t{i}", description="test",
                handler=self._echo_handler,
            )
        results = await registry.list_tools("t1", limit=5, offset=3)
        assert len(results) == 5

    # ── Update Tool ───────────────────────────────────

    @pytest.mark.asyncio
    async def test_update_description(self, registry):
        tool = await registry.register_tool(
            tenant_id="t1", name="echo",
            description="Old", handler=self._echo_handler,
        )
        await registry.update_tool(tool.tool_id, description="New")
        fetched = await registry.get_tool(tool.tool_id)
        assert fetched.description == "New"

    @pytest.mark.asyncio
    async def test_update_tags(self, registry):
        tool = await registry.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", handler=self._echo_handler,
        )
        await registry.update_tool(tool.tool_id, tags=["new"])
        fetched = await registry.get_tool(tool.tool_id)
        assert fetched.tags == ["new"]

    @pytest.mark.asyncio
    async def test_update_status(self, registry):
        tool = await registry.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", handler=self._echo_handler,
        )
        await registry.update_tool(tool.tool_id, status=ToolStatus.DEPRECATED.value)
        fetched = await registry.get_tool(tool.tool_id)
        assert fetched.status == ToolStatus.DEPRECATED.value

    @pytest.mark.asyncio
    async def test_update_not_found(self, registry):
        with pytest.raises(ToolNotFoundException):
            await registry.update_tool("nonexistent", description="test")

    # ── Invoke Tool ───────────────────────────────────

    @pytest.mark.asyncio
    async def test_invoke_success(self, registry):
        tool = await registry.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", handler=self._echo_handler,
            parameters=[ToolParameter(name="text", param_type="string", required=True)],
        )
        result = await registry.invoke_tool(tool.tool_id, {"text": "hello"})
        assert result.success
        assert result.result == "Echo: hello"

    @pytest.mark.asyncio
    async def test_invoke_missing_required(self, registry):
        tool = await registry.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", handler=self._echo_handler,
            parameters=[ToolParameter(name="text", param_type="string", required=True)],
        )
        with pytest.raises(ToolSchemaValidationException):
            await registry.invoke_tool(tool.tool_id, {})

    @pytest.mark.asyncio
    async def test_invoke_type_error(self, registry):
        tool = await registry.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", handler=self._echo_handler,
            parameters=[ToolParameter(name="text", param_type="integer", required=True)],
        )
        with pytest.raises(ToolSchemaValidationException):
            await registry.invoke_tool(tool.tool_id, {"text": "not_int"})

    @pytest.mark.asyncio
    async def test_invoke_enum_violation(self, registry):
        async def handler(args):
            return args["status"]

        tool = await registry.register_tool(
            tenant_id="t1", name="set_status",
            description="Set", handler=handler,
            parameters=[ToolParameter(
                name="status", param_type="string", required=True,
                enum=["active", "inactive"],
            )],
        )
        with pytest.raises(ToolSchemaValidationException):
            await registry.invoke_tool(tool.tool_id, {"status": "deleted"})

    @pytest.mark.asyncio
    async def test_invoke_range_violation(self, registry):
        async def handler(args):
            return args["count"]

        tool = await registry.register_tool(
            tenant_id="t1", name="count",
            description="Count", handler=handler,
            parameters=[ToolParameter(
                name="count", param_type="integer", required=True,
                minimum=0, maximum=100,
            )],
        )
        with pytest.raises(ToolSchemaValidationException):
            await registry.invoke_tool(tool.tool_id, {"count": 200})

    @pytest.mark.asyncio
    async def test_invoke_pattern_violation(self, registry):
        async def handler(args):
            return args["email"]

        tool = await registry.register_tool(
            tenant_id="t1", name="validate_email",
            description="Validate", handler=handler,
            parameters=[ToolParameter(
                name="email", param_type="string", required=True,
                pattern=r"^[a-z]+@[a-z]+\.com$",
            )],
        )
        with pytest.raises(ToolSchemaValidationException):
            await registry.invoke_tool(tool.tool_id, {"email": "INVALID"})

    @pytest.mark.asyncio
    async def test_invoke_inactive_tool(self, registry):
        tool = await registry.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", handler=self._echo_handler,
        )
        await registry.update_tool(tool.tool_id, status=ToolStatus.INACTIVE.value)
        with pytest.raises(ValidationException):
            await registry.invoke_tool(tool.tool_id, {"text": "test"})

    @pytest.mark.asyncio
    async def test_invoke_default_value(self, registry):
        tool = await registry.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", handler=self._echo_handler,
            parameters=[
                ToolParameter(name="text", param_type="string", required=True),
                ToolParameter(name="repeat", param_type="integer", default_value=3),
            ],
        )
        result = await registry.invoke_tool(tool.tool_id, {"text": "hi"})
        assert result.success

    @pytest.mark.asyncio
    async def test_invoke_by_name(self, registry):
        await registry.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", handler=self._echo_handler,
            parameters=[ToolParameter(name="text", param_type="string", required=True)],
        )
        result = await registry.invoke_tool_by_name("t1", "echo", {"text": "world"})
        assert result.success
        assert result.result == "Echo: world"

    @pytest.mark.asyncio
    async def test_invoke_by_name_not_found(self, registry):
        with pytest.raises(ToolNotFoundException):
            await registry.invoke_tool_by_name("t1", "nonexistent", {})

    @pytest.mark.asyncio
    async def test_invoke_handler_error(self, registry):
        async def bad_handler(args):
            raise ValueError("something went wrong")

        tool = await registry.register_tool(
            tenant_id="t1", name="bad",
            description="Bad", handler=bad_handler,
        )
        result = await registry.invoke_tool(tool.tool_id, {})
        assert not result.success
        assert "something went wrong" in result.error

    # ── Unregister ────────────────────────────────────

    @pytest.mark.asyncio
    async def test_unregister_tool(self, registry):
        tool = await registry.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", handler=self._echo_handler,
        )
        await registry.unregister_tool(tool.tool_id)
        with pytest.raises(ToolNotFoundException):
            await registry.get_tool(tool.tool_id)

    @pytest.mark.asyncio
    async def test_unregister_not_found(self, registry):
        with pytest.raises(ToolNotFoundException):
            await registry.unregister_tool("nonexistent")

    # ── Schema Export ─────────────────────────────────

    @pytest.mark.asyncio
    async def test_export_mcp_schema(self, registry):
        await registry.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", handler=self._echo_handler,
            parameters=[ToolParameter(name="text", param_type="string", required=True)],
        )
        schema = await registry.export_mcp_schema("t1")
        assert schema["count"] == 1
        assert "tools" in schema
        assert schema["tools"][0]["name"] == "echo"

    @pytest.mark.asyncio
    async def test_export_mcp_schema_only_active(self, registry):
        tool = await registry.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", handler=self._echo_handler,
        )
        await registry.update_tool(tool.tool_id, status=ToolStatus.INACTIVE.value)
        schema = await registry.export_mcp_schema("t1")
        assert schema["count"] == 0

    @pytest.mark.asyncio
    async def test_export_tool_schema(self, registry):
        tool = await registry.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", handler=self._echo_handler,
        )
        schema = await registry.export_tool_schema(tool.tool_id)
        assert schema["name"] == "echo"

    # ── Search ────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_search_tools(self, registry):
        await registry.register_tool(
            tenant_id="t1", name="greeting",
            description="Say hello", handler=self._echo_handler,
        )
        await registry.register_tool(
            tenant_id="t1", name="calculator",
            description="Do math", handler=self._echo_handler,
        )
        results = await registry.search_tools("t1", "hello")
        assert len(results) == 1
        assert results[0].name == "greeting"

    @pytest.mark.asyncio
    async def test_search_tools_no_results(self, registry):
        results = await registry.search_tools("t1", "nonexistent")
        assert len(results) == 0

    # ── Stats ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_stats(self, registry):
        await registry.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", handler=self._echo_handler,
        )
        stats = await registry.get_stats("t1")
        assert stats["total_tools"] == 1
        assert stats["active_tools"] == 1
        assert stats["tenant_id"] == "t1"

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, registry):
        stats = await registry.get_stats("empty")
        assert stats["total_tools"] == 0

    @pytest.mark.asyncio
    async def test_health_check(self, registry):
        hc = await registry.health_check()
        assert hc["status"] == "healthy"


# ============================================================
# SandboxEngine Tests
# ============================================================

class TestSandboxEngine:
    """Tests for SandboxEngine."""

    @pytest.fixture
    def sandbox(self):
        return SandboxEngine()

    @pytest.mark.asyncio
    async def test_process_execute(self, sandbox):
        code = """
def execute(input_data):
    name = input_data.get("name", "World")
    return {"greeting": f"Hello, {name}!"}
"""
        result = await sandbox.execute(code, {"name": "Alice"}, mode="process")
        assert result.success
        assert result.result["greeting"] == "Hello, Alice!"

    @pytest.mark.asyncio
    async def test_process_execute_no_input(self, sandbox):
        code = """
def execute(input_data):
    return {"status": "ok"}
"""
        result = await sandbox.execute(code, {}, mode="process")
        assert result.success
        assert result.result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_restricted_execute(self, sandbox):
        code = """
def execute(input_data):
    return {"sum": input_data["a"] + input_data["b"]}
"""
        result = await sandbox.execute(code, {"a": 3, "b": 4}, mode="restricted")
        assert result.success
        assert result.result["sum"] == 7

    @pytest.mark.asyncio
    async def test_sandbox_timeout(self, sandbox):
        code = """
import time
def execute(input_data):
    time.sleep(10)
    return "done"
"""
        result = await sandbox.execute(code, {}, mode="process", timeout_ms=1000)
        assert not result.success
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_sandbox_error(self, sandbox):
        code = """
def execute(input_data):
    raise ValueError("test error")
"""
        result = await sandbox.execute(code, {}, mode="restricted")
        assert not result.success
        assert "test error" in result.error

    @pytest.mark.asyncio
    async def test_sandbox_no_execute(self, sandbox):
        code = """
x = 1 + 1
"""
        result = await sandbox.execute(code, {}, mode="process")
        assert not result.success

    @pytest.mark.asyncio
    async def test_execute_function(self, sandbox):
        async def my_func(args):
            return {"result": args["x"] * 2}

        result = await sandbox.execute_function(my_func, {"x": 5})
        assert result.success
        assert result.result["result"] == 10

    @pytest.mark.asyncio
    async def test_execute_function_timeout(self, sandbox):
        import asyncio as aio

        async def slow_func(args):
            await aio.sleep(10)
            return "done"

        result = await sandbox.execute_function(slow_func, {}, timeout_ms=500)
        assert not result.success
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_function_error(self, sandbox):
        async def bad_func(args):
            raise ValueError("function error")

        result = await sandbox.execute_function(bad_func, {})
        assert not result.success
        assert "function error" in result.error

    @pytest.mark.asyncio
    async def test_docker_mode_stub(self, sandbox):
        result = await sandbox.execute("", {}, mode="docker")
        assert not result.success
        assert "not yet implemented" in result.error

    @pytest.mark.asyncio
    async def test_sandbox_health_check(self, sandbox):
        hc = await sandbox.health_check()
        assert hc["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_sandbox_result_to_dict(self, sandbox):
        sr = SandboxResult(
            success=True, result={"key": "val"},
            stdout="hello", stderr="", duration_ms=100.5,
        )
        d = sr.to_dict()
        assert d["success"] is True
        assert d["result"] == {"key": "val"}
        assert "stdout" in d
        assert d["duration_ms"] == 100.5


# ============================================================
# MCPServer Tests
# ============================================================

class TestMCPServer:
    """Tests for MCPServer."""

    @pytest.fixture
    def server(self):
        srv = MCPServer()
        srv._registry._tools.clear()
        return srv

    @pytest.mark.asyncio
    async def test_tools_list(self, server):
        await server.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", handler=lambda args: "ok",
        )
        resp = await server.tools_list("t1")
        assert resp["result"]["count"] == 1

    @pytest.mark.asyncio
    async def test_tools_list_empty(self, server):
        resp = await server.tools_list("t1")
        assert resp["result"]["count"] == 0

    @pytest.mark.asyncio
    async def test_tools_call(self, server):
        await server.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", handler=lambda args: args.get("text", ""),
            parameters=[{"name": "text", "type": "string", "required": True}],
        )
        resp = await server.tools_call("t1", "echo", {"text": "hello"})
        assert resp["result"]["success"]

    @pytest.mark.asyncio
    async def test_tools_call_not_found(self, server):
        resp = await server.tools_call("t1", "nonexistent", {})
        assert "error" in resp

    @pytest.mark.asyncio
    async def test_tools_get(self, server):
        await server.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", handler=lambda args: "ok",
        )
        resp = await server.tools_get("t1", "echo")
        assert resp["result"]["name"] == "echo"

    @pytest.mark.asyncio
    async def test_tools_get_not_found(self, server):
        resp = await server.tools_get("t1", "nonexistent")
        assert "error" in resp

    @pytest.mark.asyncio
    async def test_tools_search(self, server):
        await server.register_tool(
            tenant_id="t1", name="greeting",
            description="Say hello", handler=lambda args: "ok",
        )
        resp = await server.tools_search("t1", "hello")
        assert resp["result"]["count"] == 1

    @pytest.mark.asyncio
    async def test_register_sandbox_tool(self, server):
        code = """
def execute(input_data):
    return {"result": input_data["a"] + input_data["b"]}
"""
        resp = await server.register_sandbox_tool(
            tenant_id="t1", name="add",
            description="Add numbers", code=code,
            parameters=[
                {"name": "a", "type": "integer", "required": True},
                {"name": "b", "type": "integer", "required": True},
            ],
        )
        assert resp["result"]["name"] == "add"

    @pytest.mark.asyncio
    async def test_call_sandbox_tool(self, server):
        code = """
def execute(input_data):
    return {"sum": input_data["a"] + input_data["b"]}
"""
        await server.register_sandbox_tool(
            tenant_id="t1", name="add",
            description="Add", code=code,
            parameters=[
                {"name": "a", "type": "integer", "required": True},
                {"name": "b", "type": "integer", "required": True},
            ],
        )
        resp = await server.tools_call("t1", "add", {"a": 10, "b": 20})
        assert resp["result"]["success"]
        assert resp["result"]["result"]["sum"] == 30

    @pytest.mark.asyncio
    async def test_unregister_tool(self, server):
        resp = await server.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", handler=lambda args: "ok",
        )
        tid = resp["result"]["tool_id"]
        resp = await server.unregister_tool(tid)
        assert resp["result"]["unregistered"] is True

    @pytest.mark.asyncio
    async def test_get_tool(self, server):
        resp = await server.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", handler=lambda args: "ok",
        )
        tid = resp["result"]["tool_id"]
        resp = await server.get_tool(tid)
        assert resp["result"]["name"] == "echo"

    @pytest.mark.asyncio
    async def test_get_stats(self, server):
        await server.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", handler=lambda args: "ok",
        )
        resp = await server.get_stats("t1")
        assert resp["result"]["total_tools"] == 1

    @pytest.mark.asyncio
    async def test_health_check(self, server):
        hc = await server.health_check()
        assert hc["status"] == "healthy"
        assert hc["registry"]["status"] == "healthy"
        assert hc["sandbox"]["status"] == "healthy"


# ============================================================
# MCPToolService Tests
# ============================================================

class TestMCPToolService:
    """Tests for MCPToolService."""

    @pytest.fixture
    def svc(self):
        s = MCPToolService()
        s._registry._tools.clear()
        return s

    async def _make_tool(self, svc, tenant="t1", name="echo"):
        return await svc.register_tool(
            tenant_id=tenant, name=name,
            description="Echo tool",
            parameters=[{"name": "text", "type": "string", "required": True}],
            tags=["test"],
        )

    @pytest.mark.asyncio
    async def test_register_tool(self, svc):
        result = await svc.register_tool(
            tenant_id="t1", name="echo",
            description="Echo", tags=["util"],
        )
        assert result["name"] == "echo"
        assert "tool_id" in result

    @pytest.mark.asyncio
    async def test_register_sandbox_tool(self, svc):
        code = """
def execute(input_data):
    return {"uppercase": input_data["text"].upper()}
"""
        result = await svc.register_sandbox_tool(
            tenant_id="t1", name="upper",
            description="Convert to uppercase", code=code,
            parameters=[{"name": "text", "type": "string", "required": True}],
        )
        assert result["name"] == "upper"

    @pytest.mark.asyncio
    async def test_unregister_tool(self, svc):
        tool = await self._make_tool(svc)
        result = await svc.unregister_tool(tool["tool_id"])
        assert result["unregistered"] is True

    @pytest.mark.asyncio
    async def test_get_tool(self, svc):
        tool = await self._make_tool(svc)
        result = await svc.get_tool(tool["tool_id"])
        assert result["name"] == "echo"

    @pytest.mark.asyncio
    async def test_get_tool_by_name(self, svc):
        await self._make_tool(svc)
        result = await svc.get_tool_by_name("t1", "echo")
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_tool_by_name_not_found(self, svc):
        result = await svc.get_tool_by_name("t1", "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_tools(self, svc):
        await self._make_tool(svc)
        await self._make_tool(svc, name="calc")
        results = await svc.list_tools("t1")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_tools(self, svc):
        await self._make_tool(svc)
        results = await svc.search_tools("t1", "echo")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_update_tool(self, svc):
        tool = await self._make_tool(svc)
        result = await svc.update_tool(tool["tool_id"], description="Updated")
        assert result["description"] == "Updated"

    @pytest.mark.asyncio
    async def test_invoke_tool(self, svc):
        tool = await self._make_tool(svc)
        result = await svc.invoke_tool(tool["tool_id"], {"text": "hello"})
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_invoke_tool_by_name(self, svc):
        await self._make_tool(svc)
        result = await svc.invoke_tool_by_name("t1", "echo", {"text": "world"})
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_export_mcp_schema(self, svc):
        await self._make_tool(svc)
        result = await svc.export_mcp_schema("t1")
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_export_tool_schema(self, svc):
        tool = await self._make_tool(svc)
        result = await svc.export_tool_schema(tool["tool_id"])
        assert result["name"] == "echo"

    @pytest.mark.asyncio
    async def test_tools_list(self, svc):
        await self._make_tool(svc)
        result = await svc.tools_list("t1")
        assert result["result"]["count"] == 1

    @pytest.mark.asyncio
    async def test_tools_call(self, svc):
        await self._make_tool(svc)
        result = await svc.tools_call("t1", "echo", {"text": "mcp"})
        assert result["result"]["success"] is True

    @pytest.mark.asyncio
    async def test_tools_get(self, svc):
        await self._make_tool(svc)
        result = await svc.tools_get("t1", "echo")
        assert result["result"]["name"] == "echo"

    @pytest.mark.asyncio
    async def test_tools_search(self, svc):
        await self._make_tool(svc)
        result = await svc.tools_search("t1", "echo")
        assert result["result"]["count"] == 1

    @pytest.mark.asyncio
    async def test_get_stats(self, svc):
        await self._make_tool(svc)
        stats = await svc.get_stats("t1")
        assert stats["total_tools"] == 1

    @pytest.mark.asyncio
    async def test_health_check(self, svc):
        hc = await svc.health_check()
        assert hc["status"] == "healthy"


# ============================================================
# Singleton Tests
# ============================================================

class TestSingletons:
    """Tests for singleton accessor functions."""

    def test_get_tool_registry(self):
        r1 = get_tool_registry()
        r2 = get_tool_registry()
        assert r1 is r2

    def test_get_sandbox_engine(self):
        s1 = get_sandbox_engine()
        s2 = get_sandbox_engine()
        assert s1 is s2

    def test_get_mcp_server(self):
        s1 = get_mcp_server()
        s2 = get_mcp_server()
        assert s1 is s2

    def test_get_mcp_tool_service(self):
        s1 = get_mcp_tool_service()
        s2 = get_mcp_tool_service()
        assert s1 is s2


# ============================================================
# Config Tests
# ============================================================

class TestMCPConfig:
    """Tests for MCPConfig defaults."""

    def test_mcp_config_defaults(self):
        cfg = get_config().mcp
        assert cfg.max_tools == 100
        assert cfg.max_tool_name_length == 128
        assert cfg.max_description_length == 1024
        assert cfg.sandbox_timeout_ms == 30000
        assert cfg.sandbox_mode == "process"
        assert cfg.max_input_size_bytes == 1048576
        assert cfg.max_output_size_bytes == 1048576
        assert cfg.server_port == 9100
        assert cfg.server_host == "0.0.0.0"
        assert cfg.cache_enabled is True
        assert cfg.cache_ttl_seconds == 60

    def test_mcp_config_in_app_config(self):
        cfg = get_config()
        assert isinstance(cfg.mcp, MCPConfig)


# ============================================================
# Exception Tests
# ============================================================

class TestMCPExceptions:
    """Tests for MCP-specific exceptions."""

    def test_tool_not_found(self):
        e = ToolNotFoundException("my_tool")
        assert e.code == "NOT_FOUND"
        assert e.status_code == 404
        assert "my_tool" in str(e)

    def test_tool_execution_exception(self):
        e = ToolExecutionException("calc", "division by zero")
        assert e.code == "TOOL_EXECUTION_ERROR"
        assert e.status_code == 500
        assert "calc" in str(e)
        assert "division by zero" in str(e)

    def test_sandbox_exception(self):
        e = SandboxException("timeout exceeded")
        assert e.code == "SANDBOX_ERROR"
        assert e.status_code == 500
        assert "timeout exceeded" in str(e)

    def test_tool_schema_validation_exception(self):
        e = ToolSchemaValidationException("my_tool", ["Missing param: x"])
        assert e.code == "VALIDATION_ERROR"
        assert e.status_code == 422
        assert "Missing param: x" in str(e)