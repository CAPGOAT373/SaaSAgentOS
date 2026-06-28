"""
Agent OS V6.0 - Phase 8: Workflow Engine Enhanced Tests
DAG Visualization + Conditional Routing + Parallel Execution
"""
import pytest
import asyncio
import time

from agent_os.config import AppConfig, WorkflowConfig, set_config, get_config
from agent_os.core_platform.workflow_engine.models import (
    DAGNodeType, DAGNodeStatus, RouteOperator, ParallelStrategy, MergeStrategy,
    DAGEdge, DAGNode, DAGGraph, RouteResult, ParallelResult, DAGExecutionContext,
)
from agent_os.core_platform.workflow_engine.dag_visualizer import (
    DAGVisualizer, get_dag_visualizer,
)
from agent_os.core_platform.workflow_engine.condition_router import (
    ConditionRouter, get_condition_router,
)
from agent_os.core_platform.workflow_engine.parallel_executor import (
    ParallelExecutor, get_parallel_executor,
)
from agent_os.core_platform.workflow_engine.engine import (
    WorkflowEngine, get_workflow_engine,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def reset_config():
    config = AppConfig()
    config.workflow = WorkflowConfig()
    set_config(config)
    yield config


@pytest.fixture
def visualizer():
    return DAGVisualizer()


@pytest.fixture
def router():
    return ConditionRouter()


@pytest.fixture
def executor():
    return ParallelExecutor()


@pytest.fixture
def engine():
    eng = WorkflowEngine()
    eng.reset()
    yield eng
    eng.reset()


def _make_node(name, node_type="agent", depends_on=None, config=None, **kwargs):
    return DAGNode(
        name=name, node_type=node_type,
        depends_on=depends_on or [],
        config=config or {},
        **kwargs,
    )


def _make_edge(source, target, label="", condition=None):
    return DAGEdge(
        source_node_id=source, target_node_id=target,
        label=label, condition=condition,
    )


def _make_graph(name="test", nodes=None, edges=None):
    return DAGGraph(
        name=name, nodes=nodes or [], edges=edges or [],
    )


# ═══════════════════════════════════════════════════════════════
# Config Tests
# ═══════════════════════════════════════════════════════════════

class TestWorkflowConfig:
    def test_default_config(self):
        cfg = WorkflowConfig()
        assert cfg.max_nodes_per_workflow == 100
        assert cfg.max_parallel_branches == 20
        assert cfg.dag_validation_enabled is True
        assert cfg.visualization_format == "mermaid"
        assert cfg.parallel_execution_enabled is True
        assert cfg.parallel_max_concurrency == 50
        assert cfg.circuit_breaker_enabled is True

    def test_in_app_config(self):
        cfg = AppConfig()
        assert cfg.workflow is not None
        assert isinstance(cfg.workflow, WorkflowConfig)


# ═══════════════════════════════════════════════════════════════
# DAG Models Tests
# ═══════════════════════════════════════════════════════════════

class TestDAGModels:
    def test_dag_node_creation(self):
        node = DAGNode(name="test", node_type=DAGNodeType.AGENT.value)
        assert node.name == "test"
        assert node.node_type == "agent"
        assert node.node_id != ""

    def test_dag_node_to_dict(self):
        node = DAGNode(
            name="TestNode", node_type="condition",
            condition_expression="x > 5",
            true_branch="node_a", false_branch="node_b",
            parallel_strategy="race",
        )
        d = node.to_dict()
        assert d["name"] == "TestNode"
        assert d["condition_expression"] == "x > 5"
        assert d["true_branch"] == "node_a"
        assert d["parallel_strategy"] == "race"

    def test_dag_edge_creation(self):
        edge = DAGEdge(
            source_node_id="n1", target_node_id="n2",
            label="True", condition="inputs.x > 5",
        )
        assert edge.source_node_id == "n1"
        assert edge.label == "True"
        assert edge.condition == "inputs.x > 5"

    def test_dag_edge_to_dict(self):
        edge = DAGEdge(source_node_id="n1", target_node_id="n2", weight=0.8)
        d = edge.to_dict()
        assert d["source_node_id"] == "n1"
        assert d["weight"] == 0.8

    def test_dag_graph_creation(self):
        n1 = _make_node("Start", node_type="start")
        n2 = _make_node("End", node_type="end")
        e1 = _make_edge(n1.node_id, n2.node_id)
        graph = DAGGraph(name="test", nodes=[n1, n2], edges=[e1])
        assert graph.name == "test"
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1

    def test_dag_graph_get_node(self):
        n1 = _make_node("A")
        graph = _make_graph(nodes=[n1])
        assert graph.get_node(n1.node_id) is not None
        assert graph.get_node("nonexistent") is None

    def test_dag_graph_get_edges(self):
        n1 = _make_node("A")
        n2 = _make_node("B")
        e1 = _make_edge(n1.node_id, n2.node_id)
        graph = _make_graph(nodes=[n1, n2], edges=[e1])

        incoming = graph.get_incoming_edges(n2.node_id)
        assert len(incoming) == 1
        assert incoming[0].source_node_id == n1.node_id

        outgoing = graph.get_outgoing_edges(n1.node_id)
        assert len(outgoing) == 1
        assert outgoing[0].target_node_id == n2.node_id

    def test_dag_graph_dependencies(self):
        n1 = _make_node("A")
        n2 = _make_node("B")
        e1 = _make_edge(n1.node_id, n2.node_id)
        graph = _make_graph(nodes=[n1, n2], edges=[e1])

        deps = graph.get_direct_dependencies(n2.node_id)
        assert deps == [n1.node_id]

        dependents = graph.get_dependents(n1.node_id)
        assert dependents == [n2.node_id]

    def test_topological_sort_linear(self):
        n1 = _make_node("A")
        n2 = _make_node("B")
        n3 = _make_node("C")
        e1 = _make_edge(n1.node_id, n2.node_id)
        e2 = _make_edge(n2.node_id, n3.node_id)
        graph = _make_graph(nodes=[n1, n2, n3], edges=[e1, e2])

        sorted_nodes = graph.topological_sort()
        assert [n.name for n in sorted_nodes] == ["A", "B", "C"]

    def test_topological_sort_diamond(self):
        n1 = _make_node("A")
        n2a = _make_node("B1")
        n2b = _make_node("B2")
        n3 = _make_node("C")
        edges = [
            _make_edge(n1.node_id, n2a.node_id),
            _make_edge(n1.node_id, n2b.node_id),
            _make_edge(n2a.node_id, n3.node_id),
            _make_edge(n2b.node_id, n3.node_id),
        ]
        graph = _make_graph(nodes=[n1, n2a, n2b, n3], edges=edges)

        sorted_nodes = graph.topological_sort()
        assert sorted_nodes[0].name == "A"
        assert sorted_nodes[3].name == "C"
        assert {sorted_nodes[1].name, sorted_nodes[2].name} == {"B1", "B2"}

    def test_topological_sort_circular_raises(self):
        n1 = _make_node("A")
        n2 = _make_node("B")
        edges = [
            _make_edge(n1.node_id, n2.node_id),
            _make_edge(n2.node_id, n1.node_id),
        ]
        graph = _make_graph(nodes=[n1, n2], edges=edges)

        with pytest.raises(ValueError, match="circular"):
            graph.topological_sort()

    def test_get_levels_linear(self):
        n1 = _make_node("A")
        n2 = _make_node("B")
        n3 = _make_node("C")
        edges = [
            _make_edge(n1.node_id, n2.node_id),
            _make_edge(n2.node_id, n3.node_id),
        ]
        graph = _make_graph(nodes=[n1, n2, n3], edges=edges)

        levels = graph.get_levels()
        assert len(levels) == 3
        assert levels[0][0].name == "A"
        assert levels[1][0].name == "B"
        assert levels[2][0].name == "C"

    def test_get_levels_diamond(self):
        n1 = _make_node("A")
        n2a = _make_node("B1")
        n2b = _make_node("B2")
        n3 = _make_node("C")
        edges = [
            _make_edge(n1.node_id, n2a.node_id),
            _make_edge(n1.node_id, n2b.node_id),
            _make_edge(n2a.node_id, n3.node_id),
            _make_edge(n2b.node_id, n3.node_id),
        ]
        graph = _make_graph(nodes=[n1, n2a, n2b, n3], edges=edges)

        levels = graph.get_levels()
        assert len(levels) == 3
        assert len(levels[0]) == 1  # A
        assert len(levels[1]) == 2  # B1, B2 (parallel)
        assert len(levels[2]) == 1  # C

    def test_graph_to_dict(self):
        n1 = _make_node("A")
        graph = _make_graph(name="test", nodes=[n1])
        d = graph.to_dict()
        assert d["name"] == "test"
        assert d["node_count"] == 1
        assert d["edge_count"] == 0

    def test_route_result(self):
        result = RouteResult(
            node_id="n1", condition_passed=True,
            selected_branch="n2", skipped_branches=["n3"],
        )
        d = result.to_dict()
        assert d["condition_passed"] is True
        assert d["selected_branch"] == "n2"

    def test_parallel_result(self):
        result = ParallelResult(
            strategy="all", total_branches=3,
            completed_branches=2, failed_branches=1,
            errors=["err1"],
        )
        d = result.to_dict()
        assert d["total_branches"] == 3
        assert d["failed_branches"] == 1

    def test_dag_execution_context(self):
        ctx = DAGExecutionContext(graph_id="g1", tenant_id="t1")
        assert ctx.status == "running"
        assert ctx.is_node_done("n1") is False
        ctx.node_results["n1"] = {"result": "ok"}
        assert ctx.is_node_done("n1") is True
        assert ctx.get_node_output("n1") == "ok"


# ═══════════════════════════════════════════════════════════════
# DAG Visualizer Tests
# ═══════════════════════════════════════════════════════════════

class TestDAGVisualizer:
    def test_mermaid_linear(self, visualizer):
        n1 = _make_node("Start", node_type="start")
        n2 = _make_node("Process", node_type="agent")
        n3 = _make_node("End", node_type="end")
        edges = [
            _make_edge(n1.node_id, n2.node_id),
            _make_edge(n2.node_id, n3.node_id),
        ]
        graph = _make_graph(name="test", nodes=[n1, n2, n3], edges=edges)

        mermaid = visualizer.to_mermaid(graph, title="Test Workflow")
        assert "```mermaid" in mermaid
        assert "flowchart TD" in mermaid
        assert "Start" in mermaid
        assert "Process" in mermaid
        assert "End" in mermaid
        assert n1.node_id in mermaid
        assert n2.node_id in mermaid
        assert n3.node_id in mermaid

    def test_mermaid_condition(self, visualizer):
        n1 = _make_node("Check", node_type="condition")
        n2 = _make_node("TruePath", node_type="agent")
        n3 = _make_node("FalsePath", node_type="agent")
        edges = [
            _make_edge(n1.node_id, n2.node_id, "True"),
            _make_edge(n1.node_id, n3.node_id, "False"),
        ]
        graph = _make_graph(nodes=[n1, n2, n3], edges=edges)

        mermaid = visualizer.to_mermaid(graph)
        assert "Check" in mermaid
        assert "TruePath" in mermaid
        assert "FalsePath" in mermaid

    def test_mermaid_parallel(self, visualizer):
        n1 = _make_node("Start", node_type="start")
        n2 = _make_node("Parallel", node_type="parallel")
        n3 = _make_node("End", node_type="end")
        edges = [
            _make_edge(n1.node_id, n2.node_id),
            _make_edge(n2.node_id, n3.node_id),
        ]
        graph = _make_graph(nodes=[n1, n2, n3], edges=edges)

        mermaid = visualizer.to_mermaid(graph)
        assert "PARALLEL" in mermaid.upper()

    def test_mermaid_disabled_edge(self, visualizer):
        n1 = _make_node("A")
        n2 = _make_node("B")
        edge = _make_edge(n1.node_id, n2.node_id)
        edge.enabled = False
        graph = _make_graph(nodes=[n1, n2], edges=[edge])

        mermaid = visualizer.to_mermaid(graph)
        # Disabled edges should not appear
        assert "--> B" not in mermaid or "--> B" not in mermaid.replace(n1.node_id, "SRC").replace(n2.node_id, "B")

    def test_graphviz_output(self, visualizer):
        n1 = _make_node("A")
        n2 = _make_node("B")
        edges = [_make_edge(n1.node_id, n2.node_id)]
        graph = _make_graph(nodes=[n1, n2], edges=edges)

        dot = visualizer.to_graphviz(graph, title="Test")
        assert "digraph DAG" in dot
        assert "rankdir=TD" in dot
        assert "A" in dot
        assert "B" in dot

    def test_ascii_output(self, visualizer):
        n1 = _make_node("Start")
        n2 = _make_node("End")
        edges = [_make_edge(n1.node_id, n2.node_id)]
        graph = _make_graph(nodes=[n1, n2], edges=edges)

        ascii_art = visualizer.to_ascii(graph)
        assert "Start" in ascii_art
        assert "End" in ascii_art
        assert "Nodes: 2" in ascii_art

    def test_to_dict(self, visualizer):
        n1 = _make_node("A", node_type="agent")
        n2 = _make_node("B", node_type="delay")
        edges = [_make_edge(n1.node_id, n2.node_id)]
        graph = _make_graph(nodes=[n1, n2], edges=edges)

        result = visualizer.to_dict(graph)
        assert "mermaid" in result
        assert "graphviz" in result
        assert "ascii" in result
        assert "stats" in result
        assert result["stats"]["node_count"] == 2
        assert result["stats"]["edge_count"] == 1
        assert "agent" in result["stats"]["node_types"]
        assert "delay" in result["stats"]["node_types"]

    def test_empty_graph(self, visualizer):
        graph = _make_graph()
        mermaid = visualizer.to_mermaid(graph)
        assert "```mermaid" in mermaid

    def test_singleton(self):
        v1 = get_dag_visualizer()
        v2 = get_dag_visualizer()
        assert v1 is v2


# ═══════════════════════════════════════════════════════════════
# Condition Router Tests
# ═══════════════════════════════════════════════════════════════

class TestConditionRouter:
    def test_expression_true(self, router):
        passed, result = router.evaluate_expression("inputs['x'] > 5", {"x": 10})
        assert passed is True
        assert result is True

    def test_expression_false(self, router):
        passed, result = router.evaluate_expression("inputs['x'] > 5", {"x": 3})
        assert passed is True
        assert result is False

    def test_expression_complex(self, router):
        passed, result = router.evaluate_expression(
            "inputs['x'] > 5 and inputs['y'] < 20",
            {"x": 10, "y": 15},
        )
        assert passed is True
        assert result is True

    def test_expression_string_ops(self, router):
        passed, result = router.evaluate_expression(
            "inputs['status'] == 'active'",
            {"status": "active"},
        )
        assert passed is True
        assert result is True

    def test_expression_invalid(self, router):
        passed, result = router.evaluate_expression(
            "inputs.undefined_var.something",
            {"x": 1},
        )
        assert passed is False

    def test_expression_empty(self, router):
        passed, result = router.evaluate_expression("", {})
        assert passed is False

    def test_rule_equals(self, router):
        passed, value = router.evaluate_rule(
            {"field": "x", "operator": "eq", "value": 10},
            {"x": 10},
        )
        assert passed is True

    def test_rule_greater_than(self, router):
        passed, value = router.evaluate_rule(
            {"field": "score", "operator": "gt", "value": 0.8},
            {"score": 0.9},
        )
        assert passed is True

    def test_rule_contains(self, router):
        passed, value = router.evaluate_rule(
            {"field": "text", "operator": "contains", "value": "hello"},
            {"text": "hello world"},
        )
        assert passed is True

    def test_rule_not_contains(self, router):
        passed, value = router.evaluate_rule(
            {"field": "text", "operator": "not_contains", "value": "bad"},
            {"text": "hello world"},
        )
        assert passed is True

    def test_rule_matches_regex(self, router):
        passed, value = router.evaluate_rule(
            {"field": "email", "operator": "matches", "value": r".*@.*\..*"},
            {"email": "user@example.com"},
        )
        assert passed is True

    def test_rule_starts_with(self, router):
        passed, value = router.evaluate_rule(
            {"field": "name", "operator": "starts_with", "value": "Agent"},
            {"name": "Agent-001"},
        )
        assert passed is True

    def test_rule_compound_and(self, router):
        passed, value = router.evaluate_rule(
            {
                "operator": "and",
                "rules": [
                    {"field": "x", "operator": "gt", "value": 5},
                    {"field": "y", "operator": "lt", "value": 20},
                ],
            },
            {"x": 10, "y": 15},
        )
        assert passed is True

    def test_rule_compound_or(self, router):
        passed, value = router.evaluate_rule(
            {
                "operator": "or",
                "rules": [
                    {"field": "x", "operator": "gt", "value": 100},
                    {"field": "y", "operator": "lt", "value": 20},
                ],
            },
            {"x": 10, "y": 15},
        )
        assert passed is True  # y < 20 is True

    def test_rule_compound_not(self, router):
        passed, value = router.evaluate_rule(
            {
                "operator": "not",
                "rules": [
                    {"field": "x", "operator": "gt", "value": 5},
                ],
            },
            {"x": 3},
        )
        assert passed is True  # NOT (3 > 5) = True

    def test_condition_node_true_branch(self, router):
        node = DAGNode(
            name="Check", node_type="condition",
            condition_expression="inputs['x'] > 5",
            true_branch="node_high", false_branch="node_low",
        )
        result = router.evaluate_condition_node(node, {"x": 10})
        assert result.condition_passed is True
        assert result.selected_branch == "node_high"
        assert "node_low" in result.skipped_branches

    def test_condition_node_false_branch(self, router):
        node = DAGNode(
            name="Check", node_type="condition",
            condition_expression="inputs['x'] > 5",
            true_branch="node_high", false_branch="node_low",
        )
        result = router.evaluate_condition_node(node, {"x": 3})
        assert result.condition_passed is False
        assert result.selected_branch == "node_low"

    def test_condition_node_rule_based(self, router):
        node = DAGNode(
            name="Route", node_type="condition",
            route_rules=[
                {"field": "score", "operator": "gt", "value": 0.8, "target": "high_confidence"},
                {"field": "score", "operator": "gt", "value": 0.5, "target": "medium_confidence"},
            ],
        )
        result = router.evaluate_condition_node(node, {"score": 0.9})
        assert result.condition_passed is True
        assert result.selected_branch == "high_confidence"

    def test_condition_node_rule_fallback(self, router):
        node = DAGNode(
            name="Route", node_type="condition",
            route_rules=[
                {"field": "score", "operator": "gt", "value": 0.8, "target": "high"},
            ],
            false_branch="low",
        )
        result = router.evaluate_condition_node(node, {"score": 0.3})
        assert result.condition_passed is False
        assert result.selected_branch == "low"

    def test_edge_conditions(self, router):
        n1 = _make_node("A")
        n2 = _make_node("B")
        n3 = _make_node("C")
        edges = [
            _make_edge(n1.node_id, n2.node_id, condition="inputs['x'] > 5"),
            _make_edge(n1.node_id, n3.node_id, condition="inputs['x'] <= 5"),
        ]
        graph = _make_graph(nodes=[n1, n2, n3], edges=edges)

        active = router.evaluate_edge_conditions(graph, n1.node_id, {"x": 10})
        assert n2.node_id in active
        assert n3.node_id not in active

    def test_singleton(self):
        r1 = get_condition_router()
        r2 = get_condition_router()
        assert r1 is r2


# ═══════════════════════════════════════════════════════════════
# Parallel Executor Tests
# ═══════════════════════════════════════════════════════════════

class TestParallelExecutor:
    async def _fake_executor(self, node, context, **kwargs):
        delay = node.config.get("delay", 0.01)
        result_value = node.config.get("result", f"result_{node.name}")
        await asyncio.sleep(delay)
        return {"result": result_value, "node_id": node.node_id}

    async def _failing_executor(self, node, context, **kwargs):
        if node.config.get("fail", False):
            raise Exception(f"Node {node.name} failed")
        return {"result": f"ok_{node.name}"}

    @pytest.mark.asyncio
    async def test_execute_all_strategy(self, executor):
        nodes = [
            _make_node("A", config={"delay": 0.01}),
            _make_node("B", config={"delay": 0.01}),
            _make_node("C", config={"delay": 0.01}),
        ]
        ctx = DAGExecutionContext()
        result = await executor.execute_parallel(
            nodes, self._fake_executor, ctx, strategy="all",
        )
        assert result.total_branches == 3
        assert result.completed_branches == 3
        assert result.failed_branches == 0
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_execute_race_strategy(self, executor):
        nodes = [
            _make_node("Fast", config={"delay": 0.01}),
            _make_node("Slow", config={"delay": 0.5}),
        ]
        ctx = DAGExecutionContext()
        result = await executor.execute_parallel(
            nodes, self._fake_executor, ctx, strategy="race",
        )
        assert result.completed_branches >= 1

    @pytest.mark.asyncio
    async def test_execute_any_strategy(self, executor):
        nodes = [
            _make_node("Good", config={"delay": 0.01}),
            _make_node("Bad", config={"delay": 0.01, "fail": True}),
        ]
        ctx = DAGExecutionContext()
        result = await executor.execute_parallel(
            nodes, self._failing_executor, ctx, strategy="any",
        )
        # Should have at least one success (the first one)
        assert result.completed_branches >= 1

    @pytest.mark.asyncio
    async def test_execute_batch_strategy(self, executor):
        nodes = [_make_node(f"N{i}", config={"delay": 0.01}) for i in range(5)]
        ctx = DAGExecutionContext()
        result = await executor.execute_parallel(
            nodes, self._fake_executor, ctx, strategy="batch",
            max_concurrency=2,
        )
        assert result.total_branches == 5
        assert result.completed_branches == 5

    @pytest.mark.asyncio
    async def test_execute_with_failures(self, executor):
        nodes = [
            _make_node("A", config={"delay": 0.01}),
            _make_node("B", config={"delay": 0.01, "fail": True}),
        ]
        ctx = DAGExecutionContext()
        result = await executor.execute_parallel(
            nodes, self._failing_executor, ctx, strategy="all",
        )
        assert result.failed_branches == 1
        assert result.completed_branches == 1

    @pytest.mark.asyncio
    async def test_merge_first(self, executor):
        result = ParallelResult(
            branch_results={"a": 1, "b": 2, "c": 3},
            total_branches=3, completed_branches=3,
        )
        merged = executor.merge_results(result, strategy="first")
        assert merged == 1

    @pytest.mark.asyncio
    async def test_merge_last(self, executor):
        result = ParallelResult(
            branch_results={"a": 1, "b": 2, "c": 3},
            total_branches=3, completed_branches=3,
        )
        merged = executor.merge_results(result, strategy="last")
        assert merged == 3

    @pytest.mark.asyncio
    async def test_merge_concat_strings(self, executor):
        result = ParallelResult(
            branch_results={"a": "hello", "b": "world"},
            total_branches=2, completed_branches=2,
        )
        merged = executor.merge_results(result, strategy="concat")
        assert "hello" in merged
        assert "world" in merged

    @pytest.mark.asyncio
    async def test_merge_concat_lists(self, executor):
        result = ParallelResult(
            branch_results={"a": [1, 2], "b": [3, 4]},
            total_branches=2, completed_branches=2,
        )
        merged = executor.merge_results(result, strategy="concat")
        assert merged == [1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_merge_deep_merge(self, executor):
        result = ParallelResult(
            branch_results={"a": {"x": 1}, "b": {"y": 2}},
            total_branches=2, completed_branches=2,
        )
        merged = executor.merge_results(result, strategy="merge")
        assert merged == {"x": 1, "y": 2}

    @pytest.mark.asyncio
    async def test_merge_aggregate(self, executor):
        result = ParallelResult(
            branch_results={"a": 10, "b": 20, "c": 30},
            total_branches=3, completed_branches=3,
        )
        merged = executor.merge_results(
            result, strategy="aggregate",
            aggregate_func=lambda vals: sum(vals),
        )
        assert merged == 60

    @pytest.mark.asyncio
    async def test_merge_with_failures(self, executor):
        result = ParallelResult(
            branch_results={"a": 1, "b": Exception("fail"), "c": 3},
            total_branches=3, completed_branches=2,
        )
        merged = executor.merge_results(result, strategy="concat")
        # Exceptions should be excluded
        assert len(merged) == 2

    def test_singleton(self):
        e1 = get_parallel_executor()
        e2 = get_parallel_executor()
        assert e1 is e2


# ═══════════════════════════════════════════════════════════════
# Workflow Engine Tests
# ═══════════════════════════════════════════════════════════════

class TestWorkflowEngine:
    @pytest.mark.asyncio
    async def test_execute_linear_workflow(self, engine):
        n1 = _make_node("Start", node_type="start")
        n2 = _make_node("Process", node_type="delay", config={"seconds": 0.01})
        n3 = _make_node("End", node_type="end")
        edges = [
            _make_edge(n1.node_id, n2.node_id),
            _make_edge(n2.node_id, n3.node_id),
        ]
        graph = _make_graph(name="linear", nodes=[n1, n2, n3], edges=edges)
        engine.register_graph(graph)

        ctx = await engine.execute(graph.graph_id)
        assert ctx.status == "completed"
        assert n1.node_id in ctx.node_results
        assert n2.node_id in ctx.node_results
        assert n3.node_id in ctx.node_results

    @pytest.mark.asyncio
    async def test_execute_parallel_diamond(self, engine):
        n1 = _make_node("Start", node_type="start")
        n2a = _make_node("BranchA", node_type="delay", config={"seconds": 0.01})
        n2b = _make_node("BranchB", node_type="delay", config={"seconds": 0.01})
        n3 = _make_node("End", node_type="end")
        edges = [
            _make_edge(n1.node_id, n2a.node_id),
            _make_edge(n1.node_id, n2b.node_id),
            _make_edge(n2a.node_id, n3.node_id),
            _make_edge(n2b.node_id, n3.node_id),
        ]
        graph = _make_graph(name="diamond", nodes=[n1, n2a, n2b, n3], edges=edges)
        engine.register_graph(graph)

        ctx = await engine.execute(graph.graph_id)
        assert ctx.status == "completed"
        assert n2a.node_id in ctx.node_results
        assert n2b.node_id in ctx.node_results

    @pytest.mark.asyncio
    async def test_execute_condition_true_branch(self, engine):
        n1 = _make_node("Start", node_type="start")
        n2 = _make_node("Check", node_type="condition",
                         condition_expression="inputs.get('value', 0) > 5",
                         true_branch="high_path", false_branch="low_path")
        n3 = _make_node("HighPath", node_type="delay", config={"seconds": 0.01})
        n4 = _make_node("LowPath", node_type="delay", config={"seconds": 0.01})
        n3.node_id = "high_path"
        n4.node_id = "low_path"
        edges = [
            _make_edge(n1.node_id, n2.node_id),
            _make_edge(n2.node_id, n3.node_id),
            _make_edge(n2.node_id, n4.node_id),
        ]
        graph = _make_graph(name="condition", nodes=[n1, n2, n3, n4], edges=edges)
        engine.register_graph(graph)

        ctx = await engine.execute(graph.graph_id, input_data={"value": 10})
        assert ctx.status == "completed"
        # True branch should be executed, false branch skipped
        assert n3.node_id in ctx.node_results or n3.node_id in ctx.node_results
        route = ctx.route_decisions.get(n2.node_id)
        assert route is not None
        assert route.condition_passed is True

    @pytest.mark.asyncio
    async def test_execute_condition_false_branch(self, engine):
        n1 = _make_node("Start", node_type="start")
        n2 = _make_node("Check", node_type="condition",
                         condition_expression="inputs.get('value', 0) > 5",
                         true_branch="high_path", false_branch="low_path")
        n3 = _make_node("HighPath", node_type="delay", config={"seconds": 0.01})
        n4 = _make_node("LowPath", node_type="delay", config={"seconds": 0.01})
        n3.node_id = "high_path"
        n4.node_id = "low_path"
        edges = [
            _make_edge(n1.node_id, n2.node_id),
            _make_edge(n2.node_id, n3.node_id),
            _make_edge(n2.node_id, n4.node_id),
        ]
        graph = _make_graph(name="condition", nodes=[n1, n2, n3, n4], edges=edges)
        engine.register_graph(graph)

        ctx = await engine.execute(graph.graph_id, input_data={"value": 3})
        assert ctx.status == "completed"
        route = ctx.route_decisions.get(n2.node_id)
        assert route is not None
        assert route.condition_passed is False

    @pytest.mark.asyncio
    async def test_execute_graph_not_found(self, engine):
        with pytest.raises(ValueError, match="Graph not found"):
            await engine.execute("nonexistent")

    @pytest.mark.asyncio
    async def test_visualization(self, engine):
        n1 = _make_node("Start", node_type="start")
        n2 = _make_node("End", node_type="end")
        edges = [_make_edge(n1.node_id, n2.node_id)]
        graph = _make_graph(name="viz_test", nodes=[n1, n2], edges=edges)
        engine.register_graph(graph)

        result = await engine.visualize(graph.graph_id, format="mermaid")
        assert "mermaid" in result
        assert "Start" in result["mermaid"]

        result = await engine.visualize(graph.graph_id, format="graphviz")
        assert "graphviz" in result

        result = await engine.visualize(graph.graph_id, format="ascii")
        assert "ascii" in result

        result = await engine.visualize(graph.graph_id, format="all")
        assert "mermaid" in result
        assert "graphviz" in result
        assert "ascii" in result

    @pytest.mark.asyncio
    async def test_visualize_not_found(self, engine):
        with pytest.raises(ValueError, match="Graph not found"):
            await engine.visualize("nonexistent")

    @pytest.mark.asyncio
    async def test_graph_management(self, engine):
        graph = _make_graph(name="test")
        engine.register_graph(graph)
        assert engine.get_graph(graph.graph_id) is not None
        assert len(engine.list_graphs()) == 1

        assert engine.delete_graph(graph.graph_id) is True
        assert engine.get_graph(graph.graph_id) is None
        assert engine.delete_graph("nonexistent") is False

    @pytest.mark.asyncio
    async def test_custom_node_handler(self, engine):
        handler_called = []

        async def custom_handler(node, inputs, ctx):
            handler_called.append(node.name)
            return {"custom": "handled"}

        engine.register_node_handler("custom_type", custom_handler)

        n1 = _make_node("Custom", node_type="custom_type")
        graph = _make_graph(name="custom", nodes=[n1])
        engine.register_graph(graph)

        ctx = await engine.execute(graph.graph_id)
        assert handler_called == ["Custom"]
        assert ctx.node_results[n1.node_id]["result"] == {"custom": "handled"}

    @pytest.mark.asyncio
    async def test_node_retry(self, engine):
        call_count = [0]

        async def flaky_handler(node, inputs, ctx):
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("Temp failure")
            return {"success": True}

        n1 = _make_node("Flaky", node_type="flaky")
        n1.max_retries = 3
        engine.register_node_handler("flaky", flaky_handler)

        graph = _make_graph(name="retry", nodes=[n1])
        engine.register_graph(graph)

        ctx = await engine.execute(graph.graph_id)
        assert ctx.status == "completed"
        assert call_count[0] == 3

    @pytest.mark.asyncio
    async def test_execution_query(self, engine):
        n1 = _make_node("A", node_type="delay", config={"seconds": 0.01})
        graph = _make_graph(name="query", nodes=[n1])
        engine.register_graph(graph)

        ctx = await engine.execute(graph.graph_id)
        fetched = engine.get_execution(ctx.execution_id)
        assert fetched is not None
        assert fetched.graph_id == graph.graph_id

        executions = engine.list_executions(graph.graph_id)
        assert len(executions) == 1

    @pytest.mark.asyncio
    async def test_stats(self, engine):
        n1 = _make_node("A", node_type="delay", config={"seconds": 0.01})
        graph = _make_graph(name="stats", nodes=[n1])
        engine.register_graph(graph)

        await engine.execute(graph.graph_id)
        stats = engine.get_stats()
        assert stats["total_graphs"] == 1
        assert stats["total_executions"] == 1

    @pytest.mark.asyncio
    async def test_health_check(self, engine):
        health = await engine.health_check()
        assert health["status"] == "healthy"
        assert health["engine"] == "WorkflowEngineV6"

    @pytest.mark.asyncio
    async def test_circuit_breaker(self, engine):
        # Disable circuit breaker timeouts for testing
        engine._config = WorkflowConfig(
            circuit_breaker_enabled=True,
            circuit_breaker_threshold=2,
            circuit_breaker_timeout_seconds=3600,
        )

        async def failing_handler(node, inputs, ctx):
            raise Exception("Always fail")

        n1 = _make_node("Failing", node_type="failing")
        n1.max_retries = 0
        engine.register_node_handler("failing", failing_handler)

        graph = _make_graph(name="cb_test", nodes=[n1])
        engine.register_graph(graph)

        # First execution - failure
        ctx1 = await engine.execute(graph.graph_id)
        assert ctx1.status == "failed"

        # Second execution - failure, circuit should open
        ctx2 = await engine.execute(graph.graph_id)
        assert ctx2.status == "failed"

        # Third execution - circuit breaker should be open
        ctx3 = await engine.execute(graph.graph_id)
        assert ctx3.status == "failed"
        assert "Circuit breaker open" in ctx3.error

    def test_singleton(self):
        e1 = get_workflow_engine()
        e2 = get_workflow_engine()
        assert e1 is e2


# ═══════════════════════════════════════════════════════════════
# Integration Tests
# ═══════════════════════════════════════════════════════════════

class TestWorkflowIntegration:
    @pytest.mark.asyncio
    async def test_full_dag_workflow(self, engine):
        """Complete DAG workflow: start → parallel branches → condition → merge → end"""
        # Nodes
        start = _make_node("Start", node_type="start")
        fan_out = _make_node("FanOut", node_type="fan_out")

        branch_a = _make_node("BranchA", node_type="delay", config={"seconds": 0.01})
        branch_b = _make_node("BranchB", node_type="delay", config={"seconds": 0.01})
        branch_c = _make_node("BranchC", node_type="delay", config={"seconds": 0.01})

        condition = _make_node("RouteCheck", node_type="condition",
                                condition_expression="inputs.get('counter', 0) > 0",
                                true_branch="success_path", false_branch="retry_path")
        success = _make_node("SuccessPath", node_type="delay", config={"seconds": 0.01})
        retry = _make_node("RetryPath", node_type="delay", config={"seconds": 0.01})
        success.node_id = "success_path"
        retry.node_id = "retry_path"

        merge = _make_node("Merge", node_type="merge")
        end = _make_node("End", node_type="end")

        # Edges
        edges = [
            _make_edge(start.node_id, fan_out.node_id),
            _make_edge(fan_out.node_id, branch_a.node_id),
            _make_edge(fan_out.node_id, branch_b.node_id),
            _make_edge(fan_out.node_id, branch_c.node_id),
            _make_edge(branch_a.node_id, condition.node_id),
            _make_edge(branch_b.node_id, condition.node_id),
            _make_edge(branch_c.node_id, condition.node_id),
            _make_edge(condition.node_id, success.node_id),
            _make_edge(condition.node_id, retry.node_id),
            _make_edge(success.node_id, merge.node_id),
            _make_edge(retry.node_id, merge.node_id),
            _make_edge(merge.node_id, end.node_id),
        ]

        nodes = [start, fan_out, branch_a, branch_b, branch_c,
                 condition, success, retry, merge, end]
        graph = _make_graph(name="full_dag", nodes=nodes, edges=edges)
        engine.register_graph(graph)

        ctx = await engine.execute(graph.graph_id, input_data={"counter": 1})
        assert ctx.status == "completed"
        assert start.node_id in ctx.node_results
        assert end.node_id in ctx.node_results

        # Verify visualization
        viz = await engine.visualize(graph.graph_id, format="all")
        assert viz["stats"]["node_count"] == 10

    @pytest.mark.asyncio
    async def test_condition_routing_workflow(self, engine):
        """Workflow with conditional routing: different paths based on input."""
        start = _make_node("Start", node_type="start")
        check = _make_node("ScoreCheck", node_type="condition",
                            condition_expression="inputs.get('score', 0) >= 0.8",
                            true_branch="high_quality", false_branch="low_quality")
        high = _make_node("HighQuality", node_type="delay", config={"seconds": 0.01})
        low = _make_node("LowQuality", node_type="delay", config={"seconds": 0.01})
        high.node_id = "high_quality"
        low.node_id = "low_quality"

        edges = [
            _make_edge(start.node_id, check.node_id),
            _make_edge(check.node_id, high.node_id),
            _make_edge(check.node_id, low.node_id),
        ]

        graph = _make_graph(name="routing", nodes=[start, check, high, low], edges=edges)
        engine.register_graph(graph)

        # High score → high quality path
        ctx1 = await engine.execute(graph.graph_id, input_data={"score": 0.9})
        assert ctx1.status == "completed"
        route1 = ctx1.route_decisions[check.node_id]
        assert route1.condition_passed is True
        assert route1.selected_branch == "high_quality"

        # Low score → low quality path
        # Reset engine for second run
        engine.reset()
        engine.register_graph(graph)
        ctx2 = await engine.execute(graph.graph_id, input_data={"score": 0.3})
        assert ctx2.status == "completed"
        route2 = ctx2.route_decisions[check.node_id]
        assert route2.condition_passed is False
        assert route2.selected_branch == "low_quality"

    @pytest.mark.asyncio
    async def test_parallel_execution_performance(self, engine):
        """Verify parallel execution is faster than sequential."""
        nodes = [_make_node(f"N{i}", node_type="delay", config={"seconds": 0.05}) for i in range(4)]
        start = _make_node("Start", node_type="start")
        end = _make_node("End", node_type="end")

        edges = [_make_edge(start.node_id, n.node_id) for n in nodes]
        edges += [_make_edge(n.node_id, end.node_id) for n in nodes]

        graph = _make_graph(name="parallel_perf", nodes=[start] + nodes + [end], edges=edges)
        engine.register_graph(graph)

        start_time = time.time()
        ctx = await engine.execute(graph.graph_id)
        elapsed = time.time() - start_time

        assert ctx.status == "completed"
        # Parallel execution should be faster than sequential (4 * 0.05 = 0.2s)
        assert elapsed < 0.3  # Allow some overhead

    @pytest.mark.asyncio
    async def test_disabled_parallel_fallback(self, engine):
        """Test sequential fallback when parallel is disabled."""
        engine._config = WorkflowConfig(parallel_execution_enabled=False)

        nodes = [_make_node(f"N{i}", node_type="delay", config={"seconds": 0.01}) for i in range(3)]
        start = _make_node("Start", node_type="start")
        edges = [_make_edge(start.node_id, n.node_id) for n in nodes]
        graph = _make_graph(name="sequential", nodes=[start] + nodes, edges=edges)
        engine.register_graph(graph)

        ctx = await engine.execute(graph.graph_id)
        assert ctx.status == "completed"
        for n in nodes:
            assert n.node_id in ctx.node_results


# ═══════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════

class TestWorkflowEdgeCases:
    def test_empty_graph(self):
        graph = DAGGraph(name="empty")
        assert graph.get_levels() == []
        assert graph.topological_sort() == []

    def test_single_node_graph(self):
        n1 = _make_node("Only")
        graph = _make_graph(nodes=[n1])
        levels = graph.get_levels()
        assert len(levels) == 1
        assert len(levels[0]) == 1

    def test_disconnected_nodes(self):
        n1 = _make_node("A")
        n2 = _make_node("B")
        graph = _make_graph(nodes=[n1, n2])
        levels = graph.get_levels()
        assert len(levels) == 1  # Both in same level
        assert len(levels[0]) == 2

    def test_disabled_edge(self, visualizer):
        n1 = _make_node("A")
        n2 = _make_node("B")
        edge = _make_edge(n1.node_id, n2.node_id)
        edge.enabled = False
        graph = _make_graph(nodes=[n1, n2], edges=[edge])

        # Disabled edges should not affect topology
        levels = graph.get_levels()
        assert len(levels) == 1  # Both nodes independent

    @pytest.mark.asyncio
    async def test_condition_with_empty_branches(self, router):
        node = DAGNode(
            name="Check", node_type="condition",
            condition_expression="True",
            true_branch="", false_branch="",
        )
        result = router.evaluate_condition_node(node, {"x": 1})
        assert result.condition_passed is True
        assert result.selected_branch == ""

    @pytest.mark.asyncio
    async def test_expression_with_none_input(self, router):
        passed, result = router.evaluate_expression(
            "inputs.get('x') is not None", {"x": None},
        )
        assert passed is True
        assert result is False

    @pytest.mark.asyncio
    async def test_merge_empty_results(self, executor):
        result = ParallelResult(
            strategy="all", total_branches=0,
        )
        merged = executor.merge_results(result, strategy="first")
        assert merged is None

    def test_dag_node_all_fields(self):
        node = DAGNode(
            name="TestAll", node_type="parallel",
            condition_expression="x > 0",
            true_branch="t", false_branch="f",
            route_rules=[{"field": "x", "operator": "gt", "value": 0}],
            parallel_strategy="all", max_concurrency=5,
            fan_out_nodes=["n1", "n2"], merge_strategy="merge",
            position_x=100, position_y=200,
        )
        d = node.to_dict()
        assert d["name"] == "TestAll"
        assert d["parallel_strategy"] == "all"
        assert d["max_concurrency"] == 5
        assert len(d["fan_out_nodes"]) == 2
        assert d["merge_strategy"] == "merge"
        assert d["position_x"] == 100
        assert d["position_y"] == 200

    @pytest.mark.asyncio
    async def test_mermaid_all_node_types(self, visualizer):
        nodes = []
        for ntype in DAGNodeType:
            nodes.append(_make_node(f"{ntype.value}_node", node_type=ntype.value))
        graph = _make_graph(nodes=nodes)
        mermaid = visualizer.to_mermaid(graph)
        assert "```mermaid" in mermaid
        # Should not crash for any node type

    @pytest.mark.asyncio
    async def test_rule_unknown_operator(self, router):
        passed, value = router.evaluate_rule(
            {"field": "inputs.x", "operator": "unknown_op", "value": 1},
            {"x": 1},
        )
        assert passed is False

    @pytest.mark.asyncio
    async def test_parallel_result_to_dict(self):
        result = ParallelResult(
            strategy="all", branch_results={"a": "x" * 300},
            merged_result="y" * 300, total_branches=1,
            completed_branches=1, duration_ms=123.45,
            errors=["e1", "e2"],
        )
        d = result.to_dict()
        assert d["strategy"] == "all"
        assert d["duration_ms"] == 123.45
        assert len(d["errors"]) == 2
        # Truncated
        assert len(d["merged_result"]) <= 200