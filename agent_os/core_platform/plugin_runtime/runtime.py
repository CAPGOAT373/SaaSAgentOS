"""
Agent OS V6.0 - Plugin Runtime
Plugin sandbox execution, versioning, publishing, monetization
"""
import uuid
import subprocess
import tempfile
import os
import json
from enum import Enum
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from agent_os.core_platform.base import BaseService, ServiceContext
from agent_os.core_platform.event_bus import EventTypes
from agent_os.core_platform.exceptions import NotFoundException, ValidationException


class PluginType(str, Enum):
    TOOL = "tool"
    CONNECTOR = "connector"
    MIDDLEWARE = "middleware"
    TRANSFORM = "transform"
    CUSTOM = "custom"


class PluginStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


class SandboxMode(str, Enum):
    PROCESS = "process"       # Subprocess sandbox
    DOCKER = "docker"         # Docker container sandbox
    RESTRICTED = "restricted" # Python restricted execution


@dataclass
class PluginVersion:
    version: str = "1.0.0"
    changelog: str = ""
    published_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_active: bool = True
    dependencies: Dict[str, str] = field(default_factory=dict)
    entry_point: str = ""

    def to_dict(self) -> dict:
        return {
            "version": self.version, "changelog": self.changelog,
            "published_at": self.published_at, "is_active": self.is_active,
            "dependencies": self.dependencies, "entry_point": self.entry_point,
        }


@dataclass
class PluginAsset:
    plugin_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    developer_id: str = ""
    name: str = ""
    description: str = ""
    plugin_type: str = PluginType.TOOL.value
    status: str = PluginStatus.DRAFT.value
    price: float = 0.0
    currency: str = "USD"
    price_model: str = "free"
    versions: List[PluginVersion] = field(default_factory=list)
    current_version: str = "1.0.0"
    sandbox_mode: str = SandboxMode.PROCESS.value
    tags: List[str] = field(default_factory=list)
    category: str = ""
    total_installs: int = 0
    total_revenue: float = 0.0
    rating: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "plugin_id": self.plugin_id, "tenant_id": self.tenant_id,
            "developer_id": self.developer_id, "name": self.name,
            "description": self.description, "plugin_type": self.plugin_type,
            "status": self.status, "price": self.price, "currency": self.currency,
            "price_model": self.price_model,
            "versions": [v.to_dict() for v in self.versions],
            "current_version": self.current_version,
            "sandbox_mode": self.sandbox_mode, "tags": self.tags,
            "category": self.category, "total_installs": self.total_installs,
            "total_revenue": self.total_revenue, "rating": self.rating,
            "created_at": self.created_at, "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


class PluginRuntime(BaseService):
    """Plugin Runtime: sandbox execution, versioning, publishing"""

    def __init__(self):
        super().__init__()
        self._plugins: Dict[str, PluginAsset] = {}
        self._installed_plugins: Dict[str, List[str]] = {}  # tenant_id -> [plugin_ids]
        self._plugin_code: Dict[str, str] = {}  # plugin_id -> code

    async def register_plugin(
        self, tenant_id: str, developer_id: str, name: str, description: str,
        plugin_type: str = PluginType.TOOL.value, price: float = 0.0,
        price_model: str = "free", sandbox_mode: str = SandboxMode.PROCESS.value,
        code: str = "", tags: Optional[List[str]] = None, category: str = "",
        ctx: Optional[ServiceContext] = None
    ) -> PluginAsset:
        plugin = PluginAsset(
            tenant_id=tenant_id, developer_id=developer_id, name=name,
            description=description, plugin_type=plugin_type,
            price=price, price_model=price_model,
            sandbox_mode=sandbox_mode, tags=tags or [],
            category=category,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        v = PluginVersion(version="1.0.0", entry_point="main", changelog="Initial release")
        plugin.versions.append(v)
        plugin.current_version = "1.0.0"

        self._plugins[plugin.plugin_id] = plugin
        if code:
            self._plugin_code[plugin.plugin_id] = code

        await self.emit_event(EventTypes.PLUGIN_PUBLISHED, plugin.to_dict(), ctx)
        return plugin

    async def get_plugin(self, plugin_id: str) -> PluginAsset:
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            raise NotFoundException("Plugin", plugin_id)
        return plugin

    async def list_plugins(
        self, tenant_id: Optional[str] = None, plugin_type: Optional[str] = None,
        limit: int = 50, offset: int = 0
    ) -> List[PluginAsset]:
        plugins = list(self._plugins.values())
        if tenant_id:
            plugins = [p for p in plugins if p.tenant_id == tenant_id]
        if plugin_type:
            plugins = [p for p in plugins if p.plugin_type == plugin_type]
        return plugins[offset:offset + limit]

    async def publish_plugin(self, plugin_id: str, ctx: Optional[ServiceContext] = None) -> PluginAsset:
        plugin = await self.get_plugin(plugin_id)
        plugin.status = PluginStatus.PUBLISHED.value
        plugin.updated_at = datetime.now(timezone.utc).isoformat()
        await self.emit_event(EventTypes.PLUGIN_PUBLISHED, plugin.to_dict(), ctx)
        return plugin

    async def add_version(
        self, plugin_id: str, version: str, changelog: str,
        entry_point: str = "main", dependencies: Optional[Dict] = None,
        ctx: Optional[ServiceContext] = None
    ) -> PluginAsset:
        plugin = await self.get_plugin(plugin_id)
        v = PluginVersion(
            version=version, changelog=changelog, entry_point=entry_point,
            dependencies=dependencies or {},
        )
        plugin.versions.append(v)
        plugin.current_version = version
        plugin.updated_at = datetime.now(timezone.utc).isoformat()
        await self.emit_event(EventTypes.PLUGIN_VERSION_UPDATED, {
            "plugin_id": plugin_id, "version": version,
        }, ctx)
        return plugin

    async def install_plugin(
        self, tenant_id: str, plugin_id: str, ctx: Optional[ServiceContext] = None
    ) -> Dict[str, Any]:
        plugin = await self.get_plugin(plugin_id)
        if plugin.status != PluginStatus.PUBLISHED.value:
            raise ValidationException(f"Plugin {plugin_id} is not published")

        if tenant_id not in self._installed_plugins:
            self._installed_plugins[tenant_id] = []
        if plugin_id not in self._installed_plugins[tenant_id]:
            self._installed_plugins[tenant_id].append(plugin_id)
            plugin.total_installs += 1

        # Handle payment if plugin is paid
        if plugin.price > 0:
            from agent_os.core_platform.billing_engine import get_billing_engine
            billing = get_billing_engine()
            await billing.distribute_plugin_revenue(
                transaction_id=str(uuid.uuid4()),
                buyer_tenant_id=tenant_id,
                seller_tenant_id=plugin.tenant_id,
                total_amount=plugin.price,
                ctx=ctx,
            )
            plugin.total_revenue += plugin.price

        await self.emit_event(EventTypes.PLUGIN_INSTALLED, {
            "tenant_id": tenant_id, "plugin_id": plugin_id,
        }, ctx)
        return {"status": "installed", "plugin_id": plugin_id, "tenant_id": tenant_id}

    async def execute_plugin(
        self, plugin_id: str, input_data: Dict[str, Any],
        tenant_id: str = "", ctx: Optional[ServiceContext] = None
    ) -> Dict[str, Any]:
        plugin = await self.get_plugin(plugin_id)
        if tenant_id not in self._installed_plugins or plugin_id not in self._installed_plugins.get(tenant_id, []):
            raise ValidationException(f"Plugin {plugin_id} not installed for tenant {tenant_id}")

        code = self._plugin_code.get(plugin_id, "")
        if not code:
            raise ValidationException(f"No code found for plugin {plugin_id}")

        result = await self._sandbox_execute(code, input_data, plugin.sandbox_mode)

        await self.emit_event(EventTypes.PLUGIN_EXECUTED, {
            "plugin_id": plugin_id, "tenant_id": tenant_id,
            "input": input_data, "success": result.get("success", False),
        }, ctx)
        return result

    async def _sandbox_execute(
        self, code: str, input_data: Dict[str, Any], sandbox_mode: str
    ) -> Dict[str, Any]:
        """Execute plugin code in sandbox"""
        if sandbox_mode == SandboxMode.PROCESS.value:
            return await self._process_sandbox(code, input_data)
        elif sandbox_mode == SandboxMode.RESTRICTED.value:
            return await self._restricted_sandbox(code, input_data)
        else:
            return await self._process_sandbox(code, input_data)

    async def _process_sandbox(
        self, code: str, input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute plugin in subprocess sandbox"""
        import asyncio
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                wrapper_code = f"""
import json
import sys
import traceback

# Plugin code
{code}

# Execute
try:
    input_data = json.loads('''{json.dumps(input_data)}''')
    result = execute(input_data)
    print(json.dumps({{"success": True, "result": result}}))
except Exception as e:
    print(json.dumps({{"success": False, "error": str(e), "traceback": traceback.format_exc()}}))
"""
                f.write(wrapper_code)
                temp_path = f.name

            proc = await asyncio.create_subprocess_exec(
                "python", temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

            try:
                os.unlink(temp_path)
            except Exception:
                pass

            if stdout:
                return json.loads(stdout.decode("utf-8", errors="replace"))
            return {"success": False, "error": stderr.decode("utf-8", errors="replace") if stderr else "No output"}
        except asyncio.TimeoutError:
            return {"success": False, "error": "Plugin execution timed out (30s)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _restricted_sandbox(
        self, code: str, input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute plugin in restricted Python environment"""
        import asyncio
        try:
            safe_globals = {
                "__builtins__": {
                    "print": print, "len": len, "range": range,
                    "str": str, "int": int, "float": float, "bool": bool,
                    "list": list, "dict": dict, "tuple": tuple, "set": set,
                    "True": True, "False": False, "None": None,
                    "abs": abs, "min": min, "max": max, "sum": sum,
                    "round": round, "sorted": sorted, "enumerate": enumerate,
                    "zip": zip, "map": map, "filter": filter,
                    "isinstance": isinstance, "type": type,
                    "Exception": Exception, "ValueError": ValueError,
                    "TypeError": TypeError, "KeyError": KeyError,
                },
                "json": json,
            }
            safe_locals = {"input_data": input_data}
            exec(code, safe_globals, safe_locals)
            if "execute" in safe_locals:
                result = safe_locals["execute"](input_data)
                return {"success": True, "result": result}
            return {"success": False, "error": "No execute function found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_installed_plugins(self, tenant_id: str) -> List[PluginAsset]:
        plugin_ids = self._installed_plugins.get(tenant_id, [])
        return [self._plugins[pid] for pid in plugin_ids if pid in self._plugins]

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "service": "PluginRuntime",
            "total_plugins": len(self._plugins),
            "total_installs": sum(len(v) for v in self._installed_plugins.values()),
        }


_plugin_runtime: Optional[PluginRuntime] = None


def get_plugin_runtime() -> PluginRuntime:
    global _plugin_runtime
    if _plugin_runtime is None:
        _plugin_runtime = PluginRuntime()
    return _plugin_runtime