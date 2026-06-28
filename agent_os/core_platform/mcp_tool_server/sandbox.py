"""
Agent OS V6.0 - MCP Sandbox Engine
Safe execution environment for MCP tools
"""
import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from typing import Optional, Dict, Any, List, Callable, Awaitable

from agent_os.config import get_config
from agent_os.core_platform.exceptions import SandboxException, ValidationException


class SandboxMode:
    PROCESS = "process"
    RESTRICTED = "restricted"
    DOCKER = "docker"


class SandboxResult:
    """Result from sandbox execution."""
    def __init__(
        self, success: bool, result: Any = None,
        error: str = "", stdout: str = "", stderr: str = "",
        duration_ms: float = 0.0,
    ):
        self.success = success
        self.result = result
        self.error = error
        self.stdout = stdout
        self.stderr = stderr
        self.duration_ms = duration_ms

    def to_dict(self) -> dict:
        d = {
            "success": self.success,
            "duration_ms": round(self.duration_ms, 2),
        }
        if self.success:
            d["result"] = self.result
        else:
            d["error"] = self.error
        if self.stdout:
            d["stdout"] = self.stdout[:1000]
        if self.stderr:
            d["stderr"] = self.stderr[:1000]
        return d


class SandboxEngine:
    """
    Sandbox execution engine for MCP tools.

    Supports three modes:
    - process: Subprocess isolation (default)
    - restricted: Python restricted execution with limited builtins
    - docker: Docker container isolation (future)

    Features:
    - Timeout enforcement
    - Input/output size limits
    - Resource isolation
    - Error containment
    """

    def __init__(self):
        self._config = get_config().mcp

    async def execute(
        self, code: str, input_data: Dict[str, Any],
        mode: str = "",
        timeout_ms: Optional[int] = None,
    ) -> SandboxResult:
        """Execute code in sandbox."""
        mode = mode or self._config.sandbox_mode
        timeout = timeout_ms or self._config.sandbox_timeout_ms

        # Validate input size
        input_size = len(json.dumps(input_data).encode("utf-8"))
        if input_size > self._config.max_input_size_bytes:
            raise ValidationException(
                f"Input size {input_size} exceeds max {self._config.max_input_size_bytes}"
            )

        if mode == SandboxMode.RESTRICTED:
            return await self._restricted_execute(code, input_data, timeout)
        elif mode == SandboxMode.DOCKER:
            return await self._docker_execute(code, input_data, timeout)
        else:
            return await self._process_execute(code, input_data, timeout)

    async def execute_function(
        self, func: Callable[..., Awaitable[Any]],
        input_data: Dict[str, Any],
        timeout_ms: Optional[int] = None,
    ) -> SandboxResult:
        """Execute an async function with timeout."""
        timeout = (timeout_ms or self._config.sandbox_timeout_ms) / 1000.0
        start = time.time()

        try:
            result = await asyncio.wait_for(func(input_data), timeout=timeout)
            duration_ms = (time.time() - start) * 1000

            # Validate output size
            output_size = len(json.dumps(result).encode("utf-8"))
            if output_size > self._config.max_output_size_bytes:
                return SandboxResult(
                    success=False,
                    error=f"Output size {output_size} exceeds max {self._config.max_output_size_bytes}",
                    duration_ms=duration_ms,
                )

            return SandboxResult(
                success=True, result=result, duration_ms=duration_ms,
            )
        except asyncio.TimeoutError:
            duration_ms = (time.time() - start) * 1000
            return SandboxResult(
                success=False,
                error=f"Execution timed out after {timeout}s",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            return SandboxResult(
                success=False, error=str(e), duration_ms=duration_ms,
            )

    async def _process_execute(
        self, code: str, input_data: Dict[str, Any], timeout_ms: int,
    ) -> SandboxResult:
        """Execute code in subprocess sandbox."""
        start = time.time()
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8",
            ) as f:
                wrapper = self._build_process_wrapper(code, input_data)
                f.write(wrapper)
                temp_path = f.name

            proc = await asyncio.create_subprocess_exec(
                sys.executable, temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            timeout_seconds = timeout_ms / 1000.0
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_seconds,
            )

            try:
                os.unlink(temp_path)
            except Exception:
                pass

            stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            duration_ms = (time.time() - start) * 1000

            if stdout.strip():
                try:
                    parsed = json.loads(stdout.strip())
                    return SandboxResult(
                        success=parsed.get("success", False),
                        result=parsed.get("result"),
                        error=parsed.get("error", ""),
                        stdout=stdout,
                        stderr=stderr,
                        duration_ms=duration_ms,
                    )
                except json.JSONDecodeError:
                    return SandboxResult(
                        success=True, result=stdout.strip(),
                        stdout=stdout, stderr=stderr, duration_ms=duration_ms,
                    )

            return SandboxResult(
                success=False, error=stderr or "No output",
                stdout=stdout, stderr=stderr, duration_ms=duration_ms,
            )

        except asyncio.TimeoutError:
            duration_ms = (time.time() - start) * 1000
            return SandboxResult(
                success=False,
                error=f"Process sandbox timed out after {timeout_ms}ms",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            return SandboxResult(
                success=False, error=str(e), duration_ms=duration_ms,
            )

    def _build_process_wrapper(self, code: str, input_data: Dict[str, Any]) -> str:
        """Build a Python wrapper script for subprocess execution."""
        return f'''"""
MCP Sandbox Wrapper - Auto-generated
"""
import json
import sys
import traceback

# Input data
input_data = json.loads({json.dumps(json.dumps(input_data))})

# User code
{code}

# Execution
try:
    if "execute" in dir():
        result = execute(input_data)
        print(json.dumps({{"success": True, "result": result}}))
    else:
        print(json.dumps({{"success": False, "error": "No execute() function defined"}}))
except Exception as e:
    print(json.dumps({{
        "success": False,
        "error": str(e),
        "traceback": traceback.format_exc(),
    }}))
'''

    async def _restricted_execute(
        self, code: str, input_data: Dict[str, Any], timeout_ms: int,
    ) -> SandboxResult:
        """Execute code in restricted Python environment."""
        start = time.time()

        safe_builtins = {
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
            "json": json,
        }

        safe_globals = {"__builtins__": safe_builtins, "json": json}
        safe_locals = {"input_data": input_data}

        try:
            timeout_seconds = timeout_ms / 1000.0

            async def _exec():
                exec(code, safe_globals, safe_locals)
                if "execute" in safe_locals:
                    result = safe_locals["execute"](input_data)
                    return result
                raise ValueError("No execute() function found in code")

            result = await asyncio.wait_for(_exec(), timeout=timeout_seconds)
            duration_ms = (time.time() - start) * 1000

            output_size = len(json.dumps(result).encode("utf-8"))
            if output_size > self._config.max_output_size_bytes:
                return SandboxResult(
                    success=False,
                    error=f"Output size {output_size} exceeds max {self._config.max_output_size_bytes}",
                    duration_ms=duration_ms,
                )

            return SandboxResult(
                success=True, result=result, duration_ms=duration_ms,
            )

        except asyncio.TimeoutError:
            duration_ms = (time.time() - start) * 1000
            return SandboxResult(
                success=False,
                error=f"Restricted execution timed out after {timeout_ms}ms",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            return SandboxResult(
                success=False, error=str(e), duration_ms=duration_ms,
            )

    async def _docker_execute(
        self, code: str, input_data: Dict[str, Any], timeout_ms: int,
    ) -> SandboxResult:
        """Execute code in Docker container sandbox (stub)."""
        return SandboxResult(
            success=False,
            error="Docker sandbox mode not yet implemented. Use 'process' or 'restricted' mode.",
        )

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "service": "SandboxEngine",
            "default_mode": self._config.sandbox_mode,
            "timeout_ms": self._config.sandbox_timeout_ms,
        }


_sandbox: Optional[SandboxEngine] = None


def get_sandbox_engine() -> SandboxEngine:
    global _sandbox
    if _sandbox is None:
        _sandbox = SandboxEngine()
    return _sandbox