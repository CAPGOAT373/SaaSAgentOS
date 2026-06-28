"""
Agent OS V6.0 - WorkflowService Tests
DAG execution, parallel nodes, retry, error handling, topological sort
"""
import pytest
import asyncio

from agent_os.core_platform.exceptions import NotFoundException, ValidationException
from agent_os.services.workflow_service.service import (
    WorkflowService, WorkflowDefinition, WorkflowNode, WorkflowExecution,
    WorkflowStatus, NodeType, NodeStatus, get_workflow_service,
)


# ============================================================
# Unit Tests
# ============================================================

class TestWorkflowService:
    """WorkflowService tests with real (isolated) service."""

    @pytest.fixture
    def svc(self, isolated_workflow_service):
        return isolated_workflow_service

    def _make_node(self, name, node_type="agent", depends_on=None, config=None):
        return WorkflowNode(
            name=name, node_type=node_type,
            depends_on=depends_on or [],
            config=config or {},
        )

    # ── create_workflow ───────────────────────────────

    @pytest.mark.asyncio
    async def test_create_workflow_simple(self, svc, service_context):
        nodes = [self._make_node("Step1")]
        wf = await svc.create_workflow(
            "tenant-001", "Test WF", "A test workflow",
            nodes, ctx=service_context,
        )

        assert wf.name == "Test WF"
        assert wf.status == WorkflowStatus.DRAFT.value
        assert len(wf.nodes) == 1
        assert wf.workflow_id

    @pytest.mark.asyncio
    async def test_create_workflow_with_triggers(self, svc, service_context):
        nodes = [self._make_node("Step1")]
        wf = await svc.create_workflow(
            "tenant-001", "Event WF", "Triggered workflow",
            nodes, trigger_events=["agent.created", "webhook.received"],
            ctx=service_context,
        )

        assert len(wf.trigger_events) == 2
        assert "agent.created" in wf.trigger_events

    @pytest.mark.asyncio
    async def test_create_workflow_circular_dependency(self, svc, service_context):
        # A → B → A (circular)
        node_a = self._make_node("A", depends_on=["b-node"])
        node_b = self._make_node("B", depends_on=["a-node"])
        # Manually set IDs to match
        node_a.node_id = "a-node"
        node_b.node_id = "b-node"

        with pytest.raises(ValidationException, match="circular dependencies"):
            await svc.create_workflow(
                "tenant-001", "Circular WF", "Bad DAG",
                [node_a, node_b], ctx=service_context,
            )

    # ── get_workflow ──────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_workflow_success(self, svc, service_context):
        nodes = [self._make_node("Step1")]
        created = await svc.create_workflow(
            "tenant-001", "Get WF", "Test", nodes, ctx=service_context,
        )

        fetched = await svc.get_workflow(created.workflow_id)
        assert fetched.name == "Get WF"

    @pytest.mark.asyncio
    async def test_get_workflow_not_found(self, svc):
        with pytest.raises(NotFoundException, match="Workflow not found"):
            await svc.get_workflow("nonexistent-id")

    # ── list_workflows ────────────────────────────────

    @pytest.mark.asyncio
    async def test_list_workflows(self, svc, service_context):
        await svc.create_workflow(
            "tenant-A", "WF1", "Desc", [self._make_node("S1")], ctx=service_context,
        )
        await svc.create_workflow(
            "tenant-A", "WF2", "Desc", [self._make_node("S1")], ctx=service_context,
        )
        await svc.create_workflow(
            "tenant-B", "WF3", "Desc", [self._make_node("S1")], ctx=service_context,
        )

        a_list = await svc.list_workflows("tenant-A")
        assert len(a_list) == 2

        b_list = await svc.list_workflows("tenant-B")
        assert len(b_list) == 1

    # ── execute_workflow: linear DAG ──────────────────

    @pytest.mark.asyncio
    async def test_execute_linear_workflow(self, svc, service_context):
        node1 = self._make_node("Step1", node_type="delay", config={"seconds": 0.01})
        node2 = self._make_node("Step2", node_type="delay", config={"seconds": 0.01}, depends_on=[node1.node_id])
        node3 = self._make_node("Step3", node_type="delay", config={"seconds": 0.01}, depends_on=[node2.node_id])

        wf = await svc.create_workflow(
            "tenant-001", "Linear WF", "Sequential",
            [node1, node2, node3], ctx=service_context,
        )
        wf.status = WorkflowStatus.ACTIVE.value

        execution = await svc.execute_workflow(wf.workflow_id, ctx=service_context)

        assert execution.status == WorkflowStatus.COMPLETED.value
        assert node1.node_id in execution.node_results
        assert node2.node_id in execution.node_results
        assert node3.node_id in execution.node_results

    # ── execute_workflow: parallel DAG ────────────────

    @pytest.mark.asyncio
    async def test_execute_parallel_workflow(self, svc, service_context):
        node1 = self._make_node("Start", node_type="delay", config={"seconds": 0.01})
        node2a = self._make_node("BranchA", node_type="delay", config={"seconds": 0.01}, depends_on=[node1.node_id])
        node2b = self._make_node("BranchB", node_type="delay", config={"seconds": 0.01}, depends_on=[node1.node_id])
        node3 = self._make_node("End", node_type="delay", config={"seconds": 0.01}, depends_on=[node2a.node_id, node2b.node_id])

        wf = await svc.create_workflow(
            "tenant-001", "Parallel WF", "Diamond",
            [node1, node2a, node2b, node3], ctx=service_context,
        )
        wf.status = WorkflowStatus.ACTIVE.value

        execution = await svc.execute_workflow(wf.workflow_id, ctx=service_context)

        assert execution.status == WorkflowStatus.COMPLETED.value
        assert node1.node_id in execution.node_results
        assert node2a.node_id in execution.node_results
        assert node2b.node_id in execution.node_results
        assert node3.node_id in execution.node_results

    # ── execute_workflow: condition node ──────────────

    @pytest.mark.asyncio
    async def test_execute_condition_node(self, svc, service_context):
        node1 = self._make_node("Check", node_type="condition", config={
            "condition": "inputs.get('value', 0) > 5",
            "true_branch": "high",
            "false_branch": "low",
        })

        wf = await svc.create_workflow(
            "tenant-001", "Condition WF", "Test",
            [node1], ctx=service_context,
        )
        wf.status = WorkflowStatus.ACTIVE.value

        execution = await svc.execute_workflow(
            wf.workflow_id, input_data={"value": 10}, ctx=service_context,
        )

        assert execution.status == WorkflowStatus.COMPLETED.value
        result = execution.node_results[node1.node_id]["result"]
        assert result["result"] == "high"

    @pytest.mark.asyncio
    async def test_execute_condition_false_branch(self, svc, service_context):
        node1 = self._make_node("Check", node_type="condition", config={
            "condition": "inputs.get('value', 0) > 5",
            "true_branch": "high",
            "false_branch": "low",
        })

        wf = await svc.create_workflow(
            "tenant-001", "Condition WF", "Test",
            [node1], ctx=service_context,
        )
        wf.status = WorkflowStatus.ACTIVE.value

        execution = await svc.execute_workflow(
            wf.workflow_id, input_data={"value": 3}, ctx=service_context,
        )

        result = execution.node_results[node1.node_id]["result"]
        assert result["result"] == "low"

    # ── execute_workflow: error handling ──────────────

    @pytest.mark.asyncio
    async def test_execute_workflow_not_active(self, svc, service_context):
        node1 = self._make_node("Step1")
        wf = await svc.create_workflow(
            "tenant-001", "Cancelled WF", "Test",
            [node1], ctx=service_context,
        )
        # Set to CANCELLED - should not execute
        wf.status = WorkflowStatus.CANCELLED.value

        with pytest.raises(ValidationException, match="not active"):
            await svc.execute_workflow(wf.workflow_id, ctx=service_context)

    @pytest.mark.asyncio
    async def test_execute_workflow_not_found(self, svc, service_context):
        with pytest.raises(NotFoundException, match="Workflow not found"):
            await svc.execute_workflow("nonexistent", ctx=service_context)

    # ── get_execution ─────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_execution(self, svc, service_context):
        node1 = self._make_node("Step1", node_type="delay", config={"seconds": 0.01})
        wf = await svc.create_workflow(
            "tenant-001", "Exec WF", "Test", [node1], ctx=service_context,
        )
        wf.status = WorkflowStatus.ACTIVE.value

        execution = await svc.execute_workflow(wf.workflow_id, ctx=service_context)

        fetched = await svc.get_execution(execution.execution_id)
        assert fetched.execution_id == execution.execution_id
        assert fetched.status == WorkflowStatus.COMPLETED.value

    @pytest.mark.asyncio
    async def test_get_execution_not_found(self, svc):
        with pytest.raises(NotFoundException, match="WorkflowExecution not found"):
            await svc.get_execution("nonexistent")

    # ── topological_sort ──────────────────────────────

    def test_topological_sort_linear(self):
        node1 = self._make_node("A")
        node2 = self._make_node("B", depends_on=[node1.node_id])
        node3 = self._make_node("C", depends_on=[node2.node_id])

        wf = WorkflowDefinition(nodes=[node1, node2, node3])
        sorted_nodes = wf.topological_sort()

        assert [n.name for n in sorted_nodes] == ["A", "B", "C"]

    def test_topological_sort_diamond(self):
        node1 = self._make_node("A")
        node2a = self._make_node("B1", depends_on=[node1.node_id])
        node2b = self._make_node("B2", depends_on=[node1.node_id])
        node3 = self._make_node("C", depends_on=[node2a.node_id, node2b.node_id])

        wf = WorkflowDefinition(nodes=[node1, node2a, node2b, node3])
        sorted_nodes = wf.topological_sort()

        assert sorted_nodes[0].name == "A"
        assert sorted_nodes[3].name == "C"
        # B1 and B2 can be in any order
        assert {sorted_nodes[1].name, sorted_nodes[2].name} == {"B1", "B2"}

    def test_topological_sort_circular(self):
        node_a = self._make_node("A", depends_on=["b"])
        node_b = self._make_node("B", depends_on=["a"])
        node_a.node_id = "a"
        node_b.node_id = "b"

        wf = WorkflowDefinition(nodes=[node_a, node_b])
        with pytest.raises(ValidationException, match="circular dependencies"):
            wf.topological_sort()

    def test_topological_sort_single_node(self):
        node = self._make_node("Solo")
        wf = WorkflowDefinition(nodes=[node])
        result = wf.topological_sort()
        assert len(result) == 1
        assert result[0].name == "Solo"

    def test_topological_sort_no_dependencies(self):
        nodes = [self._make_node("A"), self._make_node("B"), self._make_node("C")]
        wf = WorkflowDefinition(nodes=nodes)
        result = wf.topological_sort()
        assert len(result) == 3

    # ── node handler registry ─────────────────────────

    @pytest.mark.asyncio
    async def test_register_node_handler(self, svc, service_context):
        handler_called = []

        async def my_handler(node, inputs, ctx):
            handler_called.append(node.name)
            return {"custom": "result"}

        svc.register_node_handler("custom_type", my_handler)

        node = self._make_node("Custom", node_type="custom_type")
        wf = await svc.create_workflow(
            "tenant-001", "Handler WF", "Test", [node], ctx=service_context,
        )
        wf.status = WorkflowStatus.ACTIVE.value

        execution = await svc.execute_workflow(wf.workflow_id, ctx=service_context)

        assert handler_called == ["Custom"]
        assert execution.node_results[node.node_id]["result"] == {"custom": "result"}

    # ── retry logic ───────────────────────────────────

    @pytest.mark.asyncio
    async def test_node_retry_on_failure(self, svc, service_context):
        call_count = 0

        async def flaky_handler(node, inputs, ctx):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return {"success": True, "attempts": call_count}

        svc.register_node_handler("flaky", flaky_handler)

        node = self._make_node("Flaky", node_type="flaky")
        node.max_retries = 3
        wf = await svc.create_workflow(
            "tenant-001", "Retry WF", "Test", [node], ctx=service_context,
        )
        wf.status = WorkflowStatus.ACTIVE.value

        execution = await svc.execute_workflow(wf.workflow_id, ctx=service_context)

        assert execution.status == WorkflowStatus.COMPLETED.value
        assert call_count == 3

    # ── health_check ──────────────────────────────────

    @pytest.mark.asyncio
    async def test_health_check(self, svc, service_context):
        await svc.create_workflow(
            "tenant-001", "W1", "Desc", [self._make_node("S1")], ctx=service_context,
        )

        result = await svc.health_check()
        assert result["status"] == "healthy"
        assert result["service"] == "WorkflowService"
        assert result["total_workflows"] == 1

    # ── dataclass serialization ───────────────────────

    def test_workflow_node_to_dict(self):
        node = WorkflowNode(
            name="TestNode", node_type="agent",
            config={"key": "value"}, depends_on=["n1", "n2"],
            max_retries=5, timeout_seconds=60,
        )
        d = node.to_dict()
        assert d["name"] == "TestNode"
        assert d["node_type"] == "agent"
        assert d["max_retries"] == 5
        assert d["timeout_seconds"] == 60

    def test_workflow_definition_to_dict(self):
        node = WorkflowNode(name="Step1")
        wf = WorkflowDefinition(
            tenant_id="t1", name="MyWF", description="Test",
            nodes=[node], trigger_events=["evt1"],
            cron_expression="0 * * * *",
        )
        d = wf.to_dict()
        assert d["name"] == "MyWF"
        assert d["trigger_events"] == ["evt1"]
        assert d["cron_expression"] == "0 * * * *"
        assert len(d["nodes"]) == 1

    def test_workflow_execution_to_dict(self):
        execution = WorkflowExecution(
            workflow_id="wf-1", tenant_id="t1",
            status="completed", error="",
        )
        d = execution.to_dict()
        assert d["workflow_id"] == "wf-1"
        assert d["status"] == "completed"

    # ── singleton ─────────────────────────────────────

    def test_singleton(self):
        svc1 = get_workflow_service()
        svc2 = get_workflow_service()
        assert svc1 is svc2