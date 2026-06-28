"""
Agent OS V6.0 - Parallel Executor
Concurrent node execution with fan-out/fan-in and result aggregation
"""
import asyncio
import time
from typing import Dict, Any, List, Optional, Callable, Awaitable, Tuple
from .models import (
    DAGNode, DAGGraph, DAGExecutionContext,
    ParallelResult, ParallelStrategy, MergeStrategy, DAGNodeStatus,
)


class ParallelExecutor:
    """
    Parallel Executor: manages concurrent execution of DAG nodes.

    Supports:
    - ALL: execute all branches concurrently, wait for all
    - ANY: execute all, return first successful result
    - RACE: race condition, first to finish wins
    - BATCH: execute in batches with concurrency limit
    - MAP: map-reduce style execution
    - Fan-out: split into N parallel branches
    - Fan-in: merge N parallel branches
    """

    def __init__(self):
        from agent_os.config import get_config
        self._config = get_config().workflow

    async def execute_parallel(
        self,
        nodes: List[DAGNode],
        executor: Callable[..., Awaitable[Dict[str, Any]]],
        context: DAGExecutionContext,
        strategy: str = ParallelStrategy.ALL.value,
        max_concurrency: int = 0,
        **kwargs,
    ) -> ParallelResult:
        """
        Execute multiple nodes in parallel.

        Args:
            nodes: List of nodes to execute
            executor: Async function to execute each node
            context: DAG execution context
            strategy: Parallel execution strategy
            max_concurrency: Max concurrent executions (0 = unlimited)
            **kwargs: Additional args passed to executor

        Returns:
            ParallelResult with branch results and merged result
        """
        if not self._config.parallel_execution_enabled:
            # Sequential fallback
            return await self._execute_sequential(nodes, executor, context, **kwargs)

        start_time = time.time()
        branch_results = {}
        errors = []

        concurrency = max_concurrency or self._config.parallel_max_concurrency
        if concurrency <= 0:
            concurrency = len(nodes)

        if strategy == ParallelStrategy.RACE.value:
            result = await self._execute_race(nodes, executor, context, **kwargs)
            branch_results = result["results"]
            errors = result["errors"]
        elif strategy == ParallelStrategy.ANY.value:
            result = await self._execute_any(nodes, executor, context, **kwargs)
            branch_results = result["results"]
            errors = result["errors"]
        elif strategy == ParallelStrategy.BATCH.value:
            result = await self._execute_batch(nodes, executor, concurrency, context, **kwargs)
            branch_results = result["results"]
            errors = result["errors"]
        elif strategy == ParallelStrategy.MAP.value:
            result = await self._execute_map(nodes, executor, context, **kwargs)
            branch_results = result["results"]
            errors = result["errors"]
        else:  # ALL (default)
            result = await self._execute_all(nodes, executor, context, **kwargs)
            branch_results = result["results"]
            errors = result["errors"]

        duration_ms = (time.time() - start_time) * 1000
        completed = sum(1 for r in branch_results.values() if not isinstance(r, Exception))
        failed = sum(1 for r in branch_results.values() if isinstance(r, Exception))

        return ParallelResult(
            strategy=strategy,
            branch_results=branch_results,
            merged_result=None,  # Will be set by merge
            total_branches=len(nodes),
            completed_branches=completed,
            failed_branches=failed,
            duration_ms=duration_ms,
            errors=errors,
        )

    async def _execute_all(
        self, nodes: List[DAGNode], executor, context, **kwargs
    ) -> Dict[str, Any]:
        """Execute all nodes concurrently, wait for all to complete."""
        tasks = []
        for node in nodes:
            task = asyncio.ensure_future(executor(node, context, **kwargs))
            tasks.append((node.node_id, task))

        results = {}
        errors = []
        for node_id, task in tasks:
            try:
                results[node_id] = await task
            except Exception as e:
                results[node_id] = e
                errors.append(str(e))

        return {"results": results, "errors": errors}

    async def _execute_race(
        self, nodes: List[DAGNode], executor, context, **kwargs
    ) -> Dict[str, Any]:
        """Execute all nodes, return first to complete."""
        tasks = []
        for node in nodes:
            task = asyncio.ensure_future(executor(node, context, **kwargs))
            tasks.append(task)

        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        # Cancel pending tasks
        for task in pending:
            task.cancel()

        results = {}
        errors = []
        for task in done:
            try:
                results["winner"] = task.result()
            except Exception as e:
                errors.append(str(e))

        return {"results": results, "errors": errors}

    async def _execute_any(
        self, nodes: List[DAGNode], executor, context, **kwargs
    ) -> Dict[str, Any]:
        """Execute all nodes, return first successful result."""
        tasks = []
        for node in nodes:
            task = asyncio.ensure_future(executor(node, context, **kwargs))
            tasks.append((node.node_id, task))

        results = {}
        errors = []
        remaining = list(tasks)

        while remaining:
            done, pending = await asyncio.wait(
                [t for _, t in remaining], return_when=asyncio.FIRST_COMPLETED
            )

            for node_id, task in list(remaining):
                if task in done:
                    remaining.remove((node_id, task))
                    try:
                        results[node_id] = task.result()
                        # First success found, cancel rest
                        for _, pt in remaining:
                            pt.cancel()
                        remaining.clear()
                        break
                    except Exception as e:
                        errors.append(str(e))

        return {"results": results, "errors": errors}

    async def _execute_batch(
        self, nodes: List[DAGNode], executor, concurrency: int,
        context, **kwargs
    ) -> Dict[str, Any]:
        """Execute nodes in batches with concurrency limit."""
        results = {}
        errors = []

        semaphore = asyncio.Semaphore(concurrency)

        async def execute_with_limit(node):
            async with semaphore:
                try:
                    return node.node_id, await executor(node, context, **kwargs)
                except Exception as e:
                    return node.node_id, e

        tasks = [execute_with_limit(node) for node in nodes]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        for item in completed:
            if isinstance(item, Exception):
                errors.append(str(item))
            else:
                node_id, result = item
                results[node_id] = result
                if isinstance(result, Exception):
                    errors.append(str(result))

        return {"results": results, "errors": errors}

    async def _execute_map(
        self, nodes: List[DAGNode], executor, context, **kwargs
    ) -> Dict[str, Any]:
        """Map-reduce style: execute all, then aggregate."""
        tasks = []
        for node in nodes:
            task = asyncio.ensure_future(executor(node, context, **kwargs))
            tasks.append((node.node_id, task))

        results = {}
        errors = []
        for node_id, task in tasks:
            try:
                results[node_id] = await task
            except Exception as e:
                results[node_id] = e
                errors.append(str(e))

        return {"results": results, "errors": errors}

    async def _execute_sequential(
        self, nodes: List[DAGNode], executor, context, **kwargs
    ) -> ParallelResult:
        """Sequential execution fallback."""
        results = {}
        errors = []
        start = time.time()

        for node in nodes:
            try:
                results[node.node_id] = await executor(node, context, **kwargs)
            except Exception as e:
                results[node.node_id] = e
                errors.append(str(e))

        duration_ms = (time.time() - start) * 1000
        completed = sum(1 for r in results.values() if not isinstance(r, Exception))
        failed = len(errors)

        return ParallelResult(
            strategy="sequential",
            branch_results=results,
            total_branches=len(nodes),
            completed_branches=completed,
            failed_branches=failed,
            duration_ms=duration_ms,
            errors=errors,
        )

    def merge_results(
        self,
        parallel_result: ParallelResult,
        strategy: str = MergeStrategy.LAST.value,
        aggregate_func: Optional[Callable] = None,
    ) -> Any:
        """
        Merge results from parallel execution.

        Args:
            parallel_result: The parallel execution result
            strategy: Merge strategy
            aggregate_func: Custom aggregation function (for AGGREGATE strategy)

        Returns:
            Merged result
        """
        results = {
            k: v for k, v in parallel_result.branch_results.items()
            if not isinstance(v, Exception)
        }

        if not results:
            return None

        if strategy == MergeStrategy.FIRST.value:
            return next(iter(results.values()))

        elif strategy == MergeStrategy.LAST.value:
            return list(results.values())[-1]

        elif strategy == MergeStrategy.CONCAT.value:
            return self._concat_results(results)

        elif strategy == MergeStrategy.MERGE.value:
            return self._deep_merge_results(results)

        elif strategy == MergeStrategy.AGGREGATE.value:
            if aggregate_func:
                return aggregate_func(list(results.values()))
            return results

        elif strategy == MergeStrategy.VOTE.value:
            return self._majority_vote(results)

        return results

    def _concat_results(self, results: Dict[str, Any]) -> Any:
        """Concatenate results."""
        values = list(results.values())
        if all(isinstance(v, str) for v in values):
            return "\n".join(values)
        if all(isinstance(v, (list, tuple)) for v in values):
            merged = []
            for v in values:
                merged.extend(v)
            return merged
        if all(isinstance(v, dict) for v in values):
            return self._deep_merge_results(results)
        return values

    def _deep_merge_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge dictionary results."""
        merged = {}
        for result in results.values():
            if isinstance(result, dict):
                merged.update(result)
        return merged

    def _majority_vote(self, results: Dict[str, Any]) -> Any:
        """Majority vote on results."""
        from collections import Counter
        values = [str(v) for v in results.values()]
        if values:
            counter = Counter(values)
            most_common = counter.most_common(1)[0]
            return most_common[0]
        return None


_executor: Optional[ParallelExecutor] = None


def get_parallel_executor() -> ParallelExecutor:
    global _executor
    if _executor is None:
        _executor = ParallelExecutor()
    return _executor