"""
Agent OS V6.0 - Workflow Service
DAG execution, streaming state, pause/resume, circuit breaker, compensation
"""
import uuid
import asyncio
import logging
from enum import Enum
from typing import Optional, Dict, Any, List, Callable, Awaitable, AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from agent_os.core_platform.base import BaseService, ServiceContext
from agent_os.core_platform.event_bus import EventTypes
from agent_os.core_platform.exceptions import NotFoundException, ValidationException

logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class NodeType(str, Enum):
    AGENT = "agent"
    TOOL = "tool"
    CONDITION = "condition"
    PARALLEL = "parallel"
    DELAY = "delay"
    HTTP = "http"
    CODE = "code"
    SUB_WORKFLOW = "sub_workflow"


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowNode:
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    node_type: str = NodeType.AGENT.value
    config: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 300
    compensation_node_id: str = ""

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id, "name": self.name,
            "node_type": self.node_type, "config": self.config,
            "depends_on": self.depends_on, "retry_count": self.retry_count,
            "max_retries": self.max_retries, "timeout_seconds": self.timeout_seconds,
        }


@dataclass
class WorkflowDefinition:
    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    description: str = ""
    status: str = WorkflowStatus.DRAFT.value
    nodes: List[WorkflowNode] = field(default_factory=list)
    trigger_events: List[str] = field(default_factory=list)
    cron_expression: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id, "tenant_id": self.tenant_id,
            "name": self.name, "description": self.description,
            "status": self.status, "nodes": [n.to_dict() for n in self.nodes],
            "trigger_events": self.trigger_events, "cron_expression": self.cron_expression,
            "created_at": self.created_at,
        }

    def topological_sort(self) -> List[WorkflowNode]:
        """Topological sort for DAG execution"""
        in_degree = {n.node_id: len(n.depends_on) for n in self.nodes}
        node_map = {n.node_id: n for n in self.nodes}
        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            nid = queue.pop(0)
            result.append(node_map[nid])
            for node in self.nodes:
                if nid in node.depends_on:
                    in_degree[node.node_id] -= 1
                    if in_degree[node.node_id] == 0:
                        queue.append(node.node_id)

        if len(result) != len(self.nodes):
            raise ValidationException("Workflow has circular dependencies")
        return result


@dataclass
class WorkflowExecution:
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    tenant_id: str = ""
    status: str = WorkflowStatus.RUNNING.value
    node_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id, "workflow_id": self.workflow_id,
            "tenant_id": self.tenant_id, "status": self.status,
            "node_results": self.node_results,
            "started_at": self.started_at, "completed_at": self.completed_at,
            "error": self.error,
        }


class CircuitBreaker:
    """Circuit breaker to prevent cascading failures"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = self.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)
        if self.failure_count >= self.failure_threshold:
            self.state = self.OPEN

    def record_success(self):
        self.failure_count = 0
        self.state = self.CLOSED

    def is_allowed(self) -> bool:
        if self.state == self.CLOSED:
            return True
        if self.state == self.OPEN:
            if self.last_failure_time:
                elapsed = (datetime.now(timezone.utc) - self.last_failure_time).total_seconds()
                if elapsed >= self.recovery_timeout:
                    self.state = self.HALF_OPEN
                    return True
            return False
        # HALF_OPEN: allow one trial
        return True


class WorkflowService(BaseService):
    """Workflow Engine V3: DAG orchestration, streaming, pause/resume, circuit breaker"""

    def __init__(self):
        super().__init__()
        self._workflows: Dict[str, WorkflowDefinition] = {}
        self._executions: Dict[str, WorkflowExecution] = {}
        self._node_handlers: Dict[str, Callable] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._pause_events: Dict[str, asyncio.Event] = {}  # execution_id -> Event

    def register_node_handler(self, node_type: str, handler: Callable):
        self._node_handlers[node_type] = handler

    async def create_workflow(
        self, tenant_id: str, name: str, description: str,
        nodes: List[WorkflowNode], trigger_events: Optional[List[str]] = None,
        ctx: Optional[ServiceContext] = None
    ) -> WorkflowDefinition:
        workflow = WorkflowDefinition(
            tenant_id=tenant_id, name=name, description=description,
            nodes=nodes, trigger_events=trigger_events or [],
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        workflow.topological_sort()
        self._workflows[workflow.workflow_id] = workflow
        await self.emit_event(EventTypes.WORKFLOW_CREATED, workflow.to_dict(), ctx)
        return workflow

    async def get_workflow(self, workflow_id: str) -> WorkflowDefinition:
        wf = self._workflows.get(workflow_id)
        if not wf:
            raise NotFoundException("Workflow", workflow_id)
        return wf

    async def list_workflows(self, tenant_id: str = "") -> List[WorkflowDefinition]:
        if tenant_id:
            return [w for w in self._workflows.values() if w.tenant_id == tenant_id]
        return list(self._workflows.values())

    async def execute_workflow(
        self, workflow_id: str, input_data: Dict[str, Any] = None,
        ctx: Optional[ServiceContext] = None
    ) -> WorkflowExecution:
        workflow = await self.get_workflow(workflow_id)
        if workflow.status not in [WorkflowStatus.ACTIVE.value, WorkflowStatus.DRAFT.value]:
            raise ValidationException(f"Workflow {workflow_id} is not active")

        execution = WorkflowExecution(
            workflow_id=workflow_id, tenant_id=workflow.tenant_id,
        )
        self._executions[execution.execution_id] = execution
        self._pause_events[execution.execution_id] = asyncio.Event()
        self._pause_events[execution.execution_id].set()  # Not paused initially

        await self.emit_event(EventTypes.WORKFLOW_STARTED, execution.to_dict(), ctx)

        try:
            sorted_nodes = workflow.topological_sort()
            node_outputs = input_data or {}

            levels = self._group_by_level(sorted_nodes, workflow)
            for level in levels:
                # Check pause
                await self._pause_events[execution.execution_id].wait()

                if execution.status == WorkflowStatus.CANCELLED.value:
                    break

                if len(level) == 1:
                    result = await self._execute_node_with_cb(
                        level[0], node_outputs, execution, workflow, ctx
                    )
                    node_outputs[level[0].node_id] = result
                else:
                    tasks = [
                        self._execute_node_with_cb(node, node_outputs, execution, workflow, ctx)
                        for node in level
                    ]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for node, result in zip(level, results):
                        if isinstance(result, Exception):
                            node_outputs[node.node_id] = {"error": str(result)}
                        else:
                            node_outputs[node.node_id] = result

            if execution.status != WorkflowStatus.CANCELLED.value:
                execution.status = WorkflowStatus.COMPLETED.value
                execution.completed_at = datetime.now(timezone.utc).isoformat()
                await self.emit_event(EventTypes.WORKFLOW_COMPLETED, execution.to_dict(), ctx)

        except Exception as e:
            execution.status = WorkflowStatus.FAILED.value
            execution.error = str(e)
            execution.completed_at = datetime.now(timezone.utc).isoformat()
            await self.emit_event(EventTypes.WORKFLOW_FAILED, execution.to_dict(), ctx)

        finally:
            self._pause_events.pop(execution.execution_id, None)

        return execution

    async def execute_workflow_stream(
        self, workflow_id: str, input_data: Dict[str, Any] = None,
        ctx: Optional[ServiceContext] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """Execute workflow with streaming state updates (SSE-compatible)"""
        workflow = await self.get_workflow(workflow_id)
        if workflow.status not in [WorkflowStatus.ACTIVE.value, WorkflowStatus.DRAFT.value]:
            raise ValidationException(f"Workflow {workflow_id} is not active")

        execution = WorkflowExecution(
            workflow_id=workflow_id, tenant_id=workflow.tenant_id,
        )
        self._executions[execution.execution_id] = execution
        self._pause_events[execution.execution_id] = asyncio.Event()
        self._pause_events[execution.execution_id].set()

        yield {"type": "workflow_started", "execution_id": execution.execution_id, "workflow_id": workflow_id}
        await self.emit_event(EventTypes.WORKFLOW_STARTED, execution.to_dict(), ctx)

        try:
            sorted_nodes = workflow.topological_sort()
            node_outputs = input_data or {}

            yield {"type": "dag_parsed", "node_count": len(sorted_nodes), "levels": len(self._group_by_level(sorted_nodes, workflow))}

            levels = self._group_by_level(sorted_nodes, workflow)
            for level_idx, level in enumerate(levels):
                await self._pause_events[execution.execution_id].wait()

                if execution.status == WorkflowStatus.CANCELLED.value:
                    yield {"type": "workflow_cancelled", "execution_id": execution.execution_id}
                    break

                yield {"type": "level_started", "level": level_idx + 1, "node_ids": [n.node_id for n in level]}

                if len(level) == 1:
                    node = level[0]
                    yield {"type": "node_executing", "node_id": node.node_id, "node_name": node.name, "node_type": node.node_type}
                    result = await self._execute_node_with_cb(node, node_outputs, execution, workflow, ctx)
                    node_outputs[node.node_id] = result
                    yield {"type": "node_completed", "node_id": node.node_id, "status": "completed" if "error" not in result else "failed"}
                else:
                    tasks = [
                        self._execute_node_with_cb(node, node_outputs, execution, workflow, ctx)
                        for node in level
                    ]
                    for node in level:
                        yield {"type": "node_executing", "node_id": node.node_id, "node_name": node.name, "node_type": node.node_type}
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for node, result in zip(level, results):
                        if isinstance(result, Exception):
                            node_outputs[node.node_id] = {"error": str(result)}
                        else:
                            node_outputs[node.node_id] = result
                        yield {"type": "node_completed", "node_id": node.node_id, "status": "completed" if not isinstance(result, Exception) and "error" not in (result or {}) else "failed"}

                yield {"type": "level_completed", "level": level_idx + 1}

            if execution.status != WorkflowStatus.CANCELLED.value:
                execution.status = WorkflowStatus.COMPLETED.value
                execution.completed_at = datetime.now(timezone.utc).isoformat()
                yield {"type": "workflow_completed", "execution_id": execution.execution_id, "node_results": execution.node_results}
                await self.emit_event(EventTypes.WORKFLOW_COMPLETED, execution.to_dict(), ctx)

        except Exception as e:
            execution.status = WorkflowStatus.FAILED.value
            execution.error = str(e)
            execution.completed_at = datetime.now(timezone.utc).isoformat()
            yield {"type": "workflow_failed", "execution_id": execution.execution_id, "error": str(e)}
            await self.emit_event(EventTypes.WORKFLOW_FAILED, execution.to_dict(), ctx)

        finally:
            self._pause_events.pop(execution.execution_id, None)

    async def pause_workflow(self, execution_id: str) -> bool:
        """Pause a running workflow execution"""
        execution = self._executions.get(execution_id)
        if not execution:
            raise NotFoundException("WorkflowExecution", execution_id)
        if execution.status != WorkflowStatus.RUNNING.value:
            raise ValidationException(f"Workflow execution {execution_id} is not running")
        execution.status = WorkflowStatus.PAUSED.value
        if execution_id in self._pause_events:
            self._pause_events[execution_id].clear()
        return True

    async def resume_workflow(self, execution_id: str) -> bool:
        """Resume a paused workflow execution"""
        execution = self._executions.get(execution_id)
        if not execution:
            raise NotFoundException("WorkflowExecution", execution_id)
        if execution.status != WorkflowStatus.PAUSED.value:
            raise ValidationException(f"Workflow execution {execution_id} is not paused")
        execution.status = WorkflowStatus.RUNNING.value
        if execution_id in self._pause_events:
            self._pause_events[execution_id].set()
        return True

    async def cancel_workflow(self, execution_id: str) -> bool:
        """Cancel a running workflow execution"""
        execution = self._executions.get(execution_id)
        if not execution:
            raise NotFoundException("WorkflowExecution", execution_id)
        execution.status = WorkflowStatus.CANCELLED.value
        if execution_id in self._pause_events:
            self._pause_events[execution_id].set()  # Unblock to allow cancellation check
        return True

    async def _execute_node_with_cb(
        self, node: WorkflowNode, inputs: Dict[str, Any],
        execution: WorkflowExecution, workflow: WorkflowDefinition,
        ctx: Optional[ServiceContext] = None
    ) -> Dict[str, Any]:
        """Execute a node with circuit breaker protection"""
        cb_key = f"{workflow.workflow_id}:{node.node_id}"
        if cb_key not in self._circuit_breakers:
            self._circuit_breakers[cb_key] = CircuitBreaker()

        cb = self._circuit_breakers[cb_key]
        if not cb.is_allowed():
            error_msg = f"Circuit breaker open for node {node.node_id}"
            logger.warning(error_msg)
            execution.node_results[node.node_id] = {
                "status": NodeStatus.FAILED.value,
                "error": error_msg,
            }
            # Try compensation node
            if node.compensation_node_id:
                comp_node = next((n for n in workflow.nodes if n.node_id == node.compensation_node_id), None)
                if comp_node:
                    logger.info(f"Executing compensation node: {comp_node.node_id}")
                    return await self._execute_node(comp_node, inputs, execution, ctx)
            raise Exception(error_msg)

        result = await self._execute_node(node, inputs, execution, ctx)

        if "error" in result:
            cb.record_failure()
        else:
            cb.record_success()

        return result

    def _group_by_level(
        self, sorted_nodes: List[WorkflowNode], workflow: WorkflowDefinition
    ) -> List[List[WorkflowNode]]:
        levels = []
        remaining = set(n.node_id for n in sorted_nodes)
        completed = set()

        while remaining:
            level = []
            for node in sorted_nodes:
                if node.node_id in remaining:
                    if all(dep in completed for dep in node.depends_on):
                        level.append(node)
            if not level:
                break
            for node in level:
                remaining.remove(node.node_id)
                completed.add(node.node_id)
            levels.append(level)

        return levels

    async def _execute_node(
        self, node: WorkflowNode, inputs: Dict[str, Any],
        execution: WorkflowExecution, ctx: Optional[ServiceContext] = None
    ) -> Dict[str, Any]:
        """Execute a single workflow node with retry logic"""
        attempts = 0
        last_error = None

        await self.emit_event(EventTypes.WORKFLOW_NODE_EXECUTING, {
            "workflow_id": execution.workflow_id,
            "execution_id": execution.execution_id,
            "node_id": node.node_id,
            "node_name": node.name,
        }, ctx)

        while attempts <= node.max_retries:
            try:
                handler = self._node_handlers.get(node.node_type)
                if handler:
                    result = await asyncio.wait_for(
                        handler(node, inputs, ctx),
                        timeout=node.timeout_seconds,
                    )
                else:
                    result = await self._default_node_executor(node, inputs, ctx)

                execution.node_results[node.node_id] = {
                    "status": NodeStatus.COMPLETED.value,
                    "result": result,
                    "attempts": attempts + 1,
                }
                await self.emit_event(EventTypes.WORKFLOW_NODE_EXECUTED, {
                    "workflow_id": execution.workflow_id,
                    "execution_id": execution.execution_id,
                    "node_id": node.node_id,
                    "status": "completed",
                }, ctx)
                return result

            except asyncio.TimeoutError:
                last_error = f"Timeout after {node.timeout_seconds}s"
                attempts += 1
            except Exception as e:
                last_error = str(e)
                attempts += 1
                if attempts <= node.max_retries:
                    await asyncio.sleep(2 ** attempts)

        execution.node_results[node.node_id] = {
            "status": NodeStatus.FAILED.value,
            "error": last_error,
            "attempts": attempts,
        }
        return {"error": last_error}

    async def _default_node_executor(
        self, node: WorkflowNode, inputs: Dict[str, Any],
        ctx: Optional[ServiceContext] = None
    ) -> Dict[str, Any]:
        """Default node execution logic"""
        if node.node_type == NodeType.AGENT.value:
            from agent_os.services.agent_service import get_agent_service
            agent_svc = get_agent_service()
            agent_id = node.config.get("agent_id", "")
            user_input = node.config.get("input", str(inputs))
            return await agent_svc.execute_agent(agent_id, user_input, ctx=ctx)

        elif node.node_type == NodeType.HTTP.value:
            url = node.config.get("url", "")
            method = node.config.get("method", "GET")
            headers = node.config.get("headers", {})
            body = node.config.get("body", None)
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.request(method, url, headers=headers, json=body) as resp:
                        return {"status": resp.status, "body": await resp.text()}
            except Exception as e:
                return {"status": "error", "body": str(e)}

        elif node.node_type == NodeType.CONDITION.value:
            condition = node.config.get("condition", "")
            true_branch = node.config.get("true_branch", "true")
            false_branch = node.config.get("false_branch", "false")
            try:
                result = eval(condition, {"__builtins__": {}}, {"inputs": inputs})
                return {"result": true_branch if result else false_branch}
            except Exception:
                return {"result": false_branch}

        elif node.node_type == NodeType.DELAY.value:
            delay_seconds = node.config.get("seconds", 1)
            await asyncio.sleep(delay_seconds)
            return {"delayed": delay_seconds}

        elif node.node_type == NodeType.CODE.value:
            code = node.config.get("code", "")
            try:
                local_vars = {"inputs": inputs, "result": None}
                exec(code, {"__builtins__": {}}, local_vars)
                return {"result": local_vars.get("result", "executed")}
            except Exception as e:
                return {"error": str(e)}

        return {"status": "executed", "node_type": node.node_type}

    async def get_execution(self, execution_id: str) -> WorkflowExecution:
        exec_data = self._executions.get(execution_id)
        if not exec_data:
            raise NotFoundException("WorkflowExecution", execution_id)
        return exec_data

    async def list_executions(self, workflow_id: str) -> List[WorkflowExecution]:
        return [e for e in self._executions.values() if e.workflow_id == workflow_id]

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "service": "WorkflowService",
            "total_workflows": len(self._workflows),
            "total_executions": len(self._executions),
            "circuit_breakers": len(self._circuit_breakers),
        }


_workflow_service: Optional[WorkflowService] = None


def get_workflow_service() -> WorkflowService:
    global _workflow_service
    if _workflow_service is None:
        _workflow_service = WorkflowService()
    return _workflow_service