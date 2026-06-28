"""
Agent OS V6.0 - Enhanced Workflow Engine
DAG visualization + conditional routing + parallel execution
"""
import asyncio
import time
from typing import Optional, Dict, Any, List, Callable, Awaitable
from datetime import datetime, timezone

from agent_os.config import get_config
from .models import (
    DAGNode, DAGEdge, DAGGraph, DAGNodeType, DAGNodeStatus,
    RouteResult, ParallelResult, DAGExecutionContext,
    ParallelStrategy, MergeStrategy,
)
from .dag_visualizer import DAGVisualizer, get_dag_visualizer
from .condition_router import ConditionRouter, get_condition_router
from .parallel_executor import ParallelExecutor, get_parallel_executor


class WorkflowEngine:
    """
    Enhanced Workflow Engine V6.0.

    Features:
    - DAG visualization (Mermaid/Graphviz/ASCII)
    - Conditional routing with expression evaluation
    - Parallel execution with multiple strategies
    - Fan-out/fan-in with result merging
    - Circuit breaker pattern
    - Node-level retry with exponential backoff
    """

    def __init__(self):
        self._config = get_config().workflow
        self._visualizer: Optional[DAGVisualizer] = None
        self._router: Optional[ConditionRouter] = None
        self._executor: Optional[ParallelExecutor] = None
        self._graphs: Dict[str, DAGGraph] = {}
        self._executions: Dict[str, DAGExecutionContext] = {}
        self._node_handlers: Dict[str, Callable] = {}
        self._circuit_breakers: Dict[str, Dict[str, Any]] = {}

    async def _ensure_components(self):
        """Lazy init components."""
        if self._visualizer is None:
            self._visualizer = get_dag_visualizer()
        if self._router is None:
            self._router = get_condition_router()
        if self._executor is None:
            self._executor = get_parallel_executor()

    # ── Graph Management ──────────────────────────────

    def register_graph(self, graph: DAGGraph) -> DAGGraph:
        """Register a DAG graph."""
        if self._config.dag_validation_enabled:
            graph.topological_sort()  # Validates DAG structure
        self._graphs[graph.graph_id] = graph
        return graph

    def get_graph(self, graph_id: str) -> Optional[DAGGraph]:
        return self._graphs.get(graph_id)

    def list_graphs(self) -> List[DAGGraph]:
        return list(self._graphs.values())

    def delete_graph(self, graph_id: str) -> bool:
        if graph_id in self._graphs:
            del self._graphs[graph_id]
            return True
        return False

    # ── Visualization ─────────────────────────────────

    async def visualize(
        self, graph_id: str, format: str = "mermaid", title: str = ""
    ) -> Dict[str, Any]:
        """Generate DAG visualization."""
        await self._ensure_components()
        graph = self._graphs.get(graph_id)
        if not graph:
            raise ValueError(f"Graph not found: {graph_id}")

        if format == "mermaid":
            return {"mermaid": self._visualizer.to_mermaid(graph, title)}
        elif format == "graphviz":
            return {"graphviz": self._visualizer.to_graphviz(graph, title)}
        elif format == "ascii":
            return {"ascii": self._visualizer.to_ascii(graph)}
        else:
            return self._visualizer.to_dict(graph)

    # ── Node Handler Registration ─────────────────────

    def register_node_handler(self, node_type: str, handler: Callable):
        """Register a custom node handler."""
        self._node_handlers[node_type] = handler

    # ── Execution ─────────────────────────────────────

    async def execute(
        self,
        graph_id: str,
        input_data: Optional[Dict[str, Any]] = None,
        tenant_id: str = "",
    ) -> DAGExecutionContext:
        """
        Execute a DAG workflow.

        Execution flow:
        1. Validate graph exists
        2. Check circuit breaker
        3. Create execution context
        4. Topological sort + level grouping
        5. Execute level by level (parallel within each level)
        6. Handle conditional routing
        7. Merge parallel results
        8. Update execution status
        """
        await self._ensure_components()

        graph = self._graphs.get(graph_id)
        if not graph:
            raise ValueError(f"Graph not found: {graph_id}")

        # Circuit breaker check
        if self._config.circuit_breaker_enabled:
            if not self._check_circuit_breaker(graph_id):
                ctx = DAGExecutionContext(
                    graph_id=graph_id, tenant_id=tenant_id,
                    status="failed", error="Circuit breaker open",
                )
                ctx.completed_at = datetime.now(timezone.utc).isoformat()
                return ctx

        # Create execution context
        ctx = DAGExecutionContext(
            graph_id=graph_id, tenant_id=tenant_id,
            input_data=input_data or {},
        )
        self._executions[ctx.execution_id] = ctx
        self._trim_executions()

        try:
            levels = graph.get_levels()
            node_outputs = input_data or {}

            for level_idx, level in enumerate(levels):
                # Filter out skipped nodes
                active_nodes = [n for n in level if n.node_id not in ctx.skipped_nodes]
                if not active_nodes:
                    continue

                # Execute level
                if len(active_nodes) == 1:
                    # Single node - check if it's a condition node
                    node = active_nodes[0]
                    await self._execute_single_node(node, graph, ctx, node_outputs)
                else:
                    # Parallel execution of multiple nodes
                    await self._execute_parallel_nodes(
                        active_nodes, graph, ctx, node_outputs
                    )

            ctx.status = "completed"
            ctx.completed_at = datetime.now(timezone.utc).isoformat()
            self._reset_circuit_breaker(graph_id)

        except Exception as e:
            ctx.status = "failed"
            ctx.error = str(e)
            ctx.completed_at = datetime.now(timezone.utc).isoformat()
            self._record_circuit_failure(graph_id)

        return ctx

    async def _execute_single_node(
        self, node: DAGNode, graph: DAGGraph,
        ctx: DAGExecutionContext, node_outputs: Dict[str, Any],
    ):
        """Execute a single node, handling conditions."""
        # Check if node can be executed (all dependencies done)
        deps = graph.get_direct_dependencies(node.node_id)
        if not all(ctx.is_node_done(d) for d in deps):
            ctx.node_statuses[node.node_id] = DAGNodeStatus.WAITING.value
            return

        # Condition node - evaluate and route
        if node.node_type == DAGNodeType.CONDITION.value:
            result = self._router.evaluate_condition_node(node, node_outputs)
            ctx.route_decisions[node.node_id] = result

            # Mark skipped branches
            for skipped in result.skipped_branches:
                if skipped:
                    ctx.skipped_nodes.add(skipped)
                    self._mark_downstream_skipped(skipped, graph, ctx)

            ctx.node_results[node.node_id] = {
                "status": DAGNodeStatus.COMPLETED.value,
                "result": result.to_dict(),
            }
            node_outputs[node.node_id] = result.evaluation_result
            return

        # Regular node execution
        result = await self._execute_node_with_retry(node, node_outputs, ctx)
        ctx.node_results[node.node_id] = {
            "status": DAGNodeStatus.COMPLETED.value if "error" not in str(result) else DAGNodeStatus.FAILED.value,
            "result": result,
        }
        node_outputs[node.node_id] = result

    async def _execute_parallel_nodes(
        self, nodes: List[DAGNode], graph: DAGGraph,
        ctx: DAGExecutionContext, node_outputs: Dict[str, Any],
    ):
        """Execute multiple nodes in parallel."""
        # Check which nodes are ready
        ready_nodes = []
        for node in nodes:
            deps = graph.get_direct_dependencies(node.node_id)
            if all(ctx.is_node_done(d) for d in deps):
                ready_nodes.append(node)
            else:
                ctx.node_statuses[node.node_id] = DAGNodeStatus.WAITING.value

        if not ready_nodes:
            return

        # Determine strategy from first node (or default)
        strategy = ready_nodes[0].parallel_strategy if ready_nodes else ParallelStrategy.ALL.value

        async def node_executor(node: DAGNode, exec_ctx, **kwargs):
            return await self._execute_node_with_retry(node, node_outputs, exec_ctx)

        parallel_result = await self._executor.execute_parallel(
            ready_nodes, node_executor, ctx, strategy=strategy,
        )

        # Store results
        for node_id, result in parallel_result.branch_results.items():
            if isinstance(result, Exception):
                ctx.node_results[node_id] = {
                    "status": DAGNodeStatus.FAILED.value,
                    "result": {"error": str(result)},
                }
                node_outputs[node_id] = {"error": str(result)}
            else:
                ctx.node_results[node_id] = {
                    "status": DAGNodeStatus.COMPLETED.value,
                    "result": result,
                }
                node_outputs[node_id] = result

    async def _execute_node_with_retry(
        self, node: DAGNode, inputs: Dict[str, Any],
        ctx: DAGExecutionContext,
    ) -> Dict[str, Any]:
        """Execute a node with retry logic."""
        attempts = 0
        last_error = None

        while attempts <= node.max_retries:
            try:
                handler = self._node_handlers.get(node.node_type)
                if handler:
                    result = await asyncio.wait_for(
                        handler(node, inputs, ctx),
                        timeout=node.timeout_seconds,
                    )
                else:
                    result = await asyncio.wait_for(
                        self._default_node_executor(node, inputs),
                        timeout=node.timeout_seconds,
                    )
                return result

            except asyncio.TimeoutError:
                last_error = f"Timeout after {node.timeout_seconds}s"
                attempts += 1
            except Exception as e:
                last_error = str(e)
                attempts += 1
                if attempts <= node.max_retries:
                    backoff = min(2 ** attempts, self._config.max_retry_delay_seconds)
                    await asyncio.sleep(backoff)

        # Retries exhausted - propagate failure to trigger circuit breaker
        raise Exception(last_error)

    async def _default_node_executor(
        self, node: DAGNode, inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Default node execution logic."""
        if node.node_type == DAGNodeType.AGENT.value:
            return {"status": "executed", "node_type": "agent", "agent_id": node.config.get("agent_id", "")}

        elif node.node_type == DAGNodeType.HTTP.value:
            url = node.config.get("url", "")
            method = node.config.get("method", "GET")
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.request(method, url) as resp:
                        return {"status": resp.status, "body": await resp.text()}
            except Exception:
                return {"status": "error", "body": "HTTP request failed"}

        elif node.node_type == DAGNodeType.DELAY.value:
            delay_seconds = node.config.get("seconds", 1)
            await asyncio.sleep(min(delay_seconds, 60))
            return {"delayed": delay_seconds}

        elif node.node_type == DAGNodeType.CODE.value:
            code = node.config.get("code", "")
            try:
                safe_globals = {"__builtins__": {"len": len, "str": str, "int": int, "float": float, "list": list, "dict": dict, "range": range, "print": print}}
                safe_locals = {"inputs": inputs}
                exec(code, safe_globals, safe_locals)
                return {"result": safe_locals.get("result", None)}
            except Exception as e:
                return {"error": str(e)}

        elif node.node_type == DAGNodeType.START.value:
            return {"status": "started"}

        elif node.node_type == DAGNodeType.END.value:
            return {"status": "completed"}

        return {"status": "executed", "node_type": node.node_type}

    # ── Conditional Routing Helpers ────────────────────

    def _mark_downstream_skipped(
        self, node_id: str, graph: DAGGraph, ctx: DAGExecutionContext,
    ):
        """Recursively mark downstream nodes as skipped."""
        stack = [node_id]
        while stack:
            current = stack.pop()
            ctx.skipped_nodes.add(current)
            for edge in graph.get_outgoing_edges(current):
                if edge.target_node_id not in ctx.skipped_nodes:
                    target = graph.get_node(edge.target_node_id)
                    if target:
                        # Only skip if all incoming edges are from skipped nodes
                        incoming = graph.get_incoming_edges(edge.target_node_id)
                        if all(e.source_node_id in ctx.skipped_nodes for e in incoming):
                            stack.append(edge.target_node_id)

    # ── Circuit Breaker ───────────────────────────────

    def _check_circuit_breaker(self, graph_id: str) -> bool:
        """Check if circuit breaker is open for this graph."""
        if graph_id not in self._circuit_breakers:
            return True
        cb = self._circuit_breakers[graph_id]
        if cb["state"] == "open":
            if time.time() - cb["opened_at"] > self._config.circuit_breaker_timeout_seconds:
                cb["state"] = "half_open"
                return True
            return False
        return True

    def _record_circuit_failure(self, graph_id: str):
        """Record a failure for circuit breaker."""
        if graph_id not in self._circuit_breakers:
            self._circuit_breakers[graph_id] = {"failures": 0, "state": "closed", "opened_at": 0}
        cb = self._circuit_breakers[graph_id]
        cb["failures"] += 1
        if cb["failures"] >= self._config.circuit_breaker_threshold:
            cb["state"] = "open"
            cb["opened_at"] = time.time()

    def _reset_circuit_breaker(self, graph_id: str):
        """Reset circuit breaker on success."""
        if graph_id in self._circuit_breakers:
            self._circuit_breakers[graph_id] = {"failures": 0, "state": "closed", "opened_at": 0}

    # ── Execution Queries ─────────────────────────────

    def get_execution(self, execution_id: str) -> Optional[DAGExecutionContext]:
        return self._executions.get(execution_id)

    def list_executions(self, graph_id: str = "") -> List[DAGExecutionContext]:
        if graph_id:
            return [e for e in self._executions.values() if e.graph_id == graph_id]
        return list(self._executions.values())

    def _trim_executions(self):
        """Trim old executions to stay within retention limit."""
        max_retention = self._config.execution_history_retention
        if len(self._executions) > max_retention:
            excess = len(self._executions) - max_retention
            oldest = sorted(
                self._executions.items(),
                key=lambda x: x[1].started_at,
            )[:excess]
            for key, _ in oldest:
                self._executions.pop(key, None)

    # ── Stats & Health ────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            "total_graphs": len(self._graphs),
            "total_executions": len(self._executions),
            "total_node_handlers": len(self._node_handlers),
            "circuit_breakers": len(self._circuit_breakers),
        }

    async def health_check(self) -> Dict[str, Any]:
        """Health check."""
        return {
            "status": "healthy",
            "engine": "WorkflowEngineV6",
            **self.get_stats(),
        }

    def reset(self):
        """Reset engine state (for testing)."""
        self._graphs.clear()
        self._executions.clear()
        self._node_handlers.clear()
        self._circuit_breakers.clear()


# Singleton
_workflow_engine: Optional[WorkflowEngine] = None


def get_workflow_engine() -> WorkflowEngine:
    global _workflow_engine
    if _workflow_engine is None:
        _workflow_engine = WorkflowEngine()
    return _workflow_engine