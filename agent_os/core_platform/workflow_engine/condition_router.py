"""
Agent OS V6.0 - Conditional Router
Expression evaluation and conditional branching for workflow DAGs
"""
import re
import operator as op
from typing import Dict, Any, Optional, List, Tuple
from .models import (
    DAGNode, DAGEdge, DAGGraph, DAGExecutionContext,
    RouteResult, RouteOperator,
)


# Safe builtins for condition evaluation
SAFE_BUILTINS = {
    "True": True, "False": False, "None": None,
    "abs": abs, "min": min, "max": max, "sum": sum,
    "len": len, "str": str, "int": int, "float": float,
    "bool": bool, "list": list, "dict": dict,
    "round": round, "isinstance": isinstance,
    "any": any, "all": all,
}

# Operator mapping
OPERATOR_MAP = {
    RouteOperator.EQUALS: lambda a, b: a == b,
    RouteOperator.NOT_EQUALS: lambda a, b: a != b,
    RouteOperator.GREATER_THAN: lambda a, b: _safe_compare(a, b, op.gt),
    RouteOperator.GREATER_EQUAL: lambda a, b: _safe_compare(a, b, op.ge),
    RouteOperator.LESS_THAN: lambda a, b: _safe_compare(a, b, op.lt),
    RouteOperator.LESS_EQUAL: lambda a, b: _safe_compare(a, b, op.le),
    RouteOperator.CONTAINS: lambda a, b: str(b).lower() in str(a).lower() if a and b else False,
    RouteOperator.NOT_CONTAINS: lambda a, b: str(b).lower() not in str(a).lower() if a and b else True,
    RouteOperator.IN: lambda a, b: _safe_in(a, b),
    RouteOperator.NOT_IN: lambda a, b: not _safe_in(a, b),
    RouteOperator.STARTS_WITH: lambda a, b: str(a).startswith(str(b)) if a and b else False,
    RouteOperator.ENDS_WITH: lambda a, b: str(a).endswith(str(b)) if a and b else False,
    RouteOperator.MATCHES: lambda a, b: bool(re.search(str(b), str(a))) if a and b else False,
    RouteOperator.IS_NULL: lambda a, b: a is None,
    RouteOperator.IS_NOT_NULL: lambda a, b: a is not None,
}


def _safe_compare(a, b, compare_op):
    """Safely compare two values, handling type mismatches."""
    try:
        # Try numeric comparison
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return compare_op(a, b)
        # Try string comparison
        return compare_op(str(a), str(b))
    except (TypeError, ValueError):
        return False


def _safe_in(a, b):
    """Safely check if a is in b."""
    try:
        if isinstance(b, (list, tuple, set, dict)):
            return a in b
        return str(a) in str(b)
    except (TypeError, ValueError):
        return False


class ConditionRouter:
    """
    Conditional Router: evaluates conditions and determines routing paths.

    Supports:
    - Expression evaluation (Python-safe eval)
    - Rule-based routing (operator + field + value)
    - Compound conditions (AND/OR/NOT)
    - Edge conditions (conditional edges in DAG)
    """

    def __init__(self):
        from agent_os.config import get_config
        self._config = get_config().workflow

    def evaluate_expression(
        self, expression: str, context: Dict[str, Any]
    ) -> Tuple[bool, Any]:
        """
        Evaluate a Python expression safely.

        Args:
            expression: Python expression string
            context: Variables available to the expression

        Returns:
            (success, result) tuple
        """
        if not expression or not expression.strip():
            return False, None

        if self._config.condition_sandbox_enabled:
            if len(expression) > self._config.condition_max_expression_length:
                return False, f"Expression too long: {len(expression)} chars"

        try:
            # Build safe eval context
            eval_context = {"inputs": context, **SAFE_BUILTINS}
            result = eval(expression, {"__builtins__": {}}, eval_context)
            return True, result
        except Exception as e:
            return False, str(e)

    def evaluate_rule(
        self, rule: Dict[str, Any], context: Dict[str, Any]
    ) -> Tuple[bool, Any]:
        """
        Evaluate a routing rule.

        Rule format:
        {
            "field": "inputs.result.score",
            "operator": "gt",
            "value": 0.8,
            "target": "node_high_confidence"
        }
        or compound:
        {
            "operator": "and",
            "rules": [...]
        }
        """
        rule_op = rule.get("operator", "eq")

        # Compound rules
        if rule_op in (RouteOperator.AND.value, RouteOperator.OR.value, RouteOperator.NOT.value):
            return self._evaluate_compound(rule, context)

        # Simple rule
        field = rule.get("field", "")
        value = rule.get("value")
        op_name = rule_op

        field_value = self._resolve_field(field, context)
        try:
            route_op = RouteOperator(op_name)
        except ValueError:
            return False, f"Unknown operator: {op_name}"
        op_func = OPERATOR_MAP.get(route_op)
        if op_func is None:
            return False, f"Unknown operator: {op_name}"

        result = op_func(field_value, value)
        return result, field_value

    def _evaluate_compound(
        self, rule: Dict[str, Any], context: Dict[str, Any]
    ) -> Tuple[bool, Any]:
        """Evaluate compound AND/OR/NOT rules."""
        op_name = rule.get("operator", "and")
        sub_rules = rule.get("rules", [])
        results = []

        for sub_rule in sub_rules:
            passed, value = self.evaluate_rule(sub_rule, context)
            results.append((passed, value))

        if op_name == RouteOperator.AND.value:
            return all(r[0] for r in results), results
        elif op_name == RouteOperator.OR.value:
            return any(r[0] for r in results), results
        elif op_name == RouteOperator.NOT.value:
            if results:
                return not results[0][0], results
            return True, results
        return False, results

    def evaluate_condition_node(
        self, node: DAGNode, context: Dict[str, Any]
    ) -> RouteResult:
        """
        Evaluate a condition node and determine the routing path.

        Args:
            node: The condition node to evaluate
            context: Current execution context variables

        Returns:
            RouteResult with selected branch
        """
        # Try expression evaluation first
        if node.condition_expression:
            passed, result = self.evaluate_expression(
                node.condition_expression, context
            )
            if passed:
                # Expression evaluated successfully - use its truth value
                condition_true = bool(result)
                selected = node.true_branch if condition_true else node.false_branch
                skipped = [node.false_branch] if condition_true else [node.true_branch]
            else:
                # Expression evaluation failed - fallback to false branch
                condition_true = False
                selected = node.false_branch
                skipped = [node.true_branch] if node.true_branch else []
            return RouteResult(
                node_id=node.node_id,
                condition_passed=condition_true,
                selected_branch=selected,
                skipped_branches=[s for s in skipped if s],
                evaluation_result=result,
            )

        # Try rule-based routing
        if node.route_rules:
            for rule in node.route_rules:
                passed, value = self.evaluate_rule(rule, context)
                if passed:
                    target = rule.get("target", "")
                    return RouteResult(
                        node_id=node.node_id,
                        condition_passed=True,
                        selected_branch=target,
                        skipped_branches=[],
                        evaluation_result=value,
                    )
            # No rule matched - use false branch
            return RouteResult(
                node_id=node.node_id,
                condition_passed=False,
                selected_branch=node.false_branch,
                skipped_branches=[node.true_branch] if node.true_branch else [],
                evaluation_result=None,
            )

        # No condition configured
        return RouteResult(
            node_id=node.node_id,
            condition_passed=False,
            selected_branch="",
            evaluation_result=None,
        )

    def evaluate_edge_conditions(
        self, graph: DAGGraph, node_id: str, context: Dict[str, Any]
    ) -> List[str]:
        """
        Evaluate outgoing edge conditions and return active target nodes.

        Args:
            graph: The DAG graph
            node_id: Source node ID
            context: Execution context

        Returns:
            List of target node IDs for edges whose conditions passed
        """
        active_targets = []
        edges = graph.get_outgoing_edges(node_id)

        for edge in edges:
            if not edge.condition:
                active_targets.append(edge.target_node_id)
                continue

            passed, result = self.evaluate_expression(edge.condition, context)
            if passed and result:
                active_targets.append(edge.target_node_id)

        return active_targets

    def _resolve_field(self, field: str, context: Dict[str, Any]) -> Any:
        """Resolve a dotted field path from context."""
        parts = field.split(".")
        value = context
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                return None
        return value


_router: Optional[ConditionRouter] = None


def get_condition_router() -> ConditionRouter:
    global _router
    if _router is None:
        _router = ConditionRouter()
    return _router