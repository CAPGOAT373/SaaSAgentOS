"""
Agent OS V6.0 - Workflow Engine Models
Enhanced DAG models: nodes, edges, graph, routing, execution states
"""
import uuid
from enum import Enum
from typing import Optional, Dict, Any, List, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone


class DAGNodeType(str, Enum):
    """Types of DAG nodes."""
    AGENT = "agent"
    TOOL = "tool"
    CONDITION = "condition"
    PARALLEL = "parallel"
    DELAY = "delay"
    HTTP = "http"
    CODE = "code"
    SUB_WORKFLOW = "sub_workflow"
    START = "start"
    END = "end"
    FAN_OUT = "fan_out"    # splits into parallel branches
    FAN_IN = "fan_in"      # joins parallel branches
    MERGE = "merge"        # merges multiple inputs


class DAGNodeStatus(str, Enum):
    """Execution status of a DAG node."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING = "waiting"  # waiting for condition result


class RouteOperator(str, Enum):
    """Conditional routing operators."""
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    GREATER_THAN = "gt"
    GREATER_EQUAL = "ge"
    LESS_THAN = "lt"
    LESS_EQUAL = "le"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    IN = "in"
    NOT_IN = "not_in"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    MATCHES = "matches"  # regex
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    AND = "and"
    OR = "or"
    NOT = "not"


class ParallelStrategy(str, Enum):
    """Parallel execution strategies."""
    ALL = "all"             # execute all branches concurrently
    ANY = "any"             # return first successful result
    RACE = "race"           # race condition, first to finish wins
    BATCH = "batch"         # execute in batches
    MAP = "map"             # map-reduce style


class MergeStrategy(str, Enum):
    """Merge strategies for fan-in nodes."""
    FIRST = "first"          # take first result
    LAST = "last"            # take last result
    CONCAT = "concat"        # concatenate all results
    MERGE = "merge"          # deep merge all results
    AGGREGATE = "aggregate"  # custom aggregation function
    VOTE = "vote"            # majority vote


@dataclass
class DAGEdge:
    """Edge in the DAG connecting two nodes."""
    edge_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_node_id: str = ""
    target_node_id: str = ""
    label: str = ""
    condition: Optional[str] = None  # conditional edge expression
    weight: float = 1.0  # edge weight for routing priority
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "edge_id": self.edge_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "label": self.label,
            "condition": self.condition,
            "weight": self.weight,
            "enabled": self.enabled,
            "metadata": self.metadata,
        }


@dataclass
class DAGNode:
    """Enhanced DAG node with routing and parallel config."""
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    node_type: str = DAGNodeType.AGENT.value
    config: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 300
    compensation_node_id: str = ""

    # Conditional routing
    condition_expression: str = ""  # expression to evaluate
    true_branch: str = ""   # target node_id if condition is true
    false_branch: str = ""  # target node_id if condition is false
    route_rules: List[Dict[str, Any]] = field(default_factory=list)

    # Parallel execution
    parallel_strategy: str = ParallelStrategy.ALL.value
    max_concurrency: int = 0  # 0 = unlimited
    fan_out_nodes: List[str] = field(default_factory=list)
    merge_strategy: str = MergeStrategy.LAST.value

    # Position (for visualization)
    position_x: int = 0
    position_y: int = 0

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "node_type": self.node_type,
            "config": self.config,
            "depends_on": self.depends_on,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "compensation_node_id": self.compensation_node_id,
            "condition_expression": self.condition_expression,
            "true_branch": self.true_branch,
            "false_branch": self.false_branch,
            "route_rules": self.route_rules,
            "parallel_strategy": self.parallel_strategy,
            "max_concurrency": self.max_concurrency,
            "fan_out_nodes": self.fan_out_nodes,
            "merge_strategy": self.merge_strategy,
            "position_x": self.position_x,
            "position_y": self.position_y,
        }


@dataclass
class DAGGraph:
    """Complete DAG graph representation."""
    graph_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    nodes: List[DAGNode] = field(default_factory=list)
    edges: List[DAGEdge] = field(default_factory=list)
    start_node_id: str = ""
    end_node_id: str = ""
    version: str = "1.0.0"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_node(self, node_id: str) -> Optional[DAGNode]:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None

    def get_incoming_edges(self, node_id: str) -> List[DAGEdge]:
        return [e for e in self.edges if e.target_node_id == node_id and e.enabled]

    def get_outgoing_edges(self, node_id: str) -> List[DAGEdge]:
        return [e for e in self.edges if e.source_node_id == node_id and e.enabled]

    def get_direct_dependencies(self, node_id: str) -> List[str]:
        """Get node IDs that directly feed into this node."""
        return [e.source_node_id for e in self.get_incoming_edges(node_id)]

    def get_dependents(self, node_id: str) -> List[str]:
        """Get node IDs that depend on this node."""
        return [e.target_node_id for e in self.get_outgoing_edges(node_id)]

    def topological_sort(self) -> List[DAGNode]:
        """Kahn's algorithm topological sort."""
        node_map = {n.node_id: n for n in self.nodes}
        in_degree = {n.node_id: 0 for n in self.nodes}
        for edge in self.edges:
            if edge.enabled:
                in_degree[edge.target_node_id] = in_degree.get(edge.target_node_id, 0) + 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            nid = queue.pop(0)
            if nid in node_map:
                result.append(node_map[nid])
            for edge in self.get_outgoing_edges(nid):
                in_degree[edge.target_node_id] -= 1
                if in_degree[edge.target_node_id] == 0:
                    queue.append(edge.target_node_id)

        if len(result) != len(self.nodes):
            raise ValueError("DAG has circular dependencies")
        return result

    def get_levels(self) -> List[List[DAGNode]]:
        """Group nodes by execution level (parallel within each level)."""
        sorted_nodes = self.topological_sort()
        levels = []
        remaining = set(n.node_id for n in sorted_nodes)
        completed = set()

        while remaining:
            level = []
            for node in sorted_nodes:
                if node.node_id in remaining:
                    deps = self.get_direct_dependencies(node.node_id)
                    if all(d in completed for d in deps):
                        level.append(node)
            if not level:
                break
            for node in level:
                remaining.remove(node.node_id)
                completed.add(node.node_id)
            levels.append(level)
        return levels

    def to_dict(self) -> dict:
        return {
            "graph_id": self.graph_id,
            "name": self.name,
            "description": self.description,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "start_node_id": self.start_node_id,
            "end_node_id": self.end_node_id,
            "version": self.version,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


@dataclass
class RouteResult:
    """Result of conditional routing evaluation."""
    route_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    node_id: str = ""
    condition_passed: bool = False
    selected_branch: str = ""  # target node_id
    skipped_branches: List[str] = field(default_factory=list)
    evaluation_result: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "route_id": self.route_id,
            "node_id": self.node_id,
            "condition_passed": self.condition_passed,
            "selected_branch": self.selected_branch,
            "skipped_branches": self.skipped_branches,
            "evaluation_result": str(self.evaluation_result),
            "metadata": self.metadata,
        }


@dataclass
class ParallelResult:
    """Result of parallel execution."""
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy: str = ParallelStrategy.ALL.value
    branch_results: Dict[str, Any] = field(default_factory=dict)
    merged_result: Any = None
    total_branches: int = 0
    completed_branches: int = 0
    failed_branches: int = 0
    duration_ms: float = 0.0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "strategy": self.strategy,
            "branch_results": {k: str(v)[:200] for k, v in self.branch_results.items()},
            "merged_result": str(self.merged_result)[:200] if self.merged_result else None,
            "total_branches": self.total_branches,
            "completed_branches": self.completed_branches,
            "failed_branches": self.failed_branches,
            "duration_ms": round(self.duration_ms, 2),
            "errors": self.errors,
        }


@dataclass
class DAGExecutionContext:
    """Runtime execution context for a DAG workflow."""
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    graph_id: str = ""
    tenant_id: str = ""
    status: str = "running"
    node_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    node_statuses: Dict[str, str] = field(default_factory=dict)
    route_decisions: Dict[str, RouteResult] = field(default_factory=dict)
    skipped_nodes: Set[str] = field(default_factory=set)
    input_data: Dict[str, Any] = field(default_factory=dict)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str = ""
    error: str = ""

    def is_node_done(self, node_id: str) -> bool:
        return node_id in self.node_results or node_id in self.skipped_nodes

    def get_node_output(self, node_id: str) -> Optional[Any]:
        if node_id in self.node_results:
            result = self.node_results[node_id].get("result", {})
            if isinstance(result, dict):
                return result.get("result", result)
            return result
        return None

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "graph_id": self.graph_id,
            "tenant_id": self.tenant_id,
            "status": self.status,
            "node_results": self.node_results,
            "node_statuses": self.node_statuses,
            "route_decisions": {k: v.to_dict() for k, v in self.route_decisions.items()},
            "skipped_nodes": list(self.skipped_nodes),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }