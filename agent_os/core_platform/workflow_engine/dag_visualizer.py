"""
Agent OS V6.0 - DAG Visualizer
Generates Mermaid and Graphviz visualizations from DAG graphs
"""
from typing import Optional, List, Dict, Any
from .models import DAGGraph, DAGNode, DAGNodeType, DAGEdge


class DAGVisualizer:
    """
    DAG Visualizer: generates visual representations of workflow DAGs.

    Supports:
    - Mermaid (flowchart/graph TD)
    - Graphviz (DOT format)
    - ASCII art (text-based)
    """

    # Mermaid styling per node type
    NODE_STYLES: Dict[str, Dict[str, str]] = {
        DAGNodeType.START.value: {"shape": "circle", "fill": "#4CAF50", "color": "#fff"},
        DAGNodeType.END.value: {"shape": "circle", "fill": "#F44336", "color": "#fff"},
        DAGNodeType.AGENT.value: {"shape": "rect", "fill": "#2196F3", "color": "#fff"},
        DAGNodeType.TOOL.value: {"shape": "rect", "fill": "#FF9800", "color": "#fff"},
        DAGNodeType.CONDITION.value: {"shape": "diamond", "fill": "#9C27B0", "color": "#fff"},
        DAGNodeType.PARALLEL.value: {"shape": "hexagon", "fill": "#00BCD4", "color": "#fff"},
        DAGNodeType.FAN_OUT.value: {"shape": "trapezoid", "fill": "#009688", "color": "#fff"},
        DAGNodeType.FAN_IN.value: {"shape": "inv_trapezoid", "fill": "#009688", "color": "#fff"},
        DAGNodeType.MERGE.value: {"shape": "subroutine", "fill": "#607D8B", "color": "#fff"},
        DAGNodeType.DELAY.value: {"shape": "stadium", "fill": "#795548", "color": "#fff"},
        DAGNodeType.HTTP.value: {"shape": "rect", "fill": "#3F51B5", "color": "#fff"},
        DAGNodeType.CODE.value: {"shape": "rect", "fill": "#E91E63", "color": "#fff"},
        DAGNodeType.SUB_WORKFLOW.value: {"shape": "subroutine", "fill": "#8BC34A", "color": "#fff"},
    }

    def __init__(self):
        from agent_os.config import get_config
        self._config = get_config().workflow

    def to_mermaid(self, graph: DAGGraph, title: str = "",
                   show_conditions: bool = True, show_labels: bool = True) -> str:
        """
        Generate a Mermaid flowchart diagram.

        Args:
            graph: The DAG graph to visualize
            title: Optional diagram title
            show_conditions: Whether to show edge conditions
            show_labels: Whether to show node labels on edges

        Returns:
            Mermaid syntax string
        """
        lines = ["```mermaid", "flowchart TD"]
        if title:
            lines.append(f"  title[{title}]")

        # Node definitions with styling
        node_ids = set()
        for node in graph.nodes:
            node_ids.add(node.node_id)
            style = self.NODE_STYLES.get(node.node_type, {"shape": "rect", "fill": "#9E9E9E", "color": "#fff"})
            node_label = self._escape_label(node.name or node.node_id[:8])
            node_type_label = node.node_type.upper()

            if node.node_type == DAGNodeType.CONDITION.value:
                lines.append(f'  {node.node_id}{{{{{node_label}<br/>[{node_type_label}]}}}}')
            elif node.node_type in (DAGNodeType.START.value, DAGNodeType.END.value):
                lines.append(f'  {node.node_id}(("{node_label}"))')
            elif node.node_type == DAGNodeType.PARALLEL.value:
                lines.append(f'  {node.node_id}{{{{{node_label}<br/>[{node_type_label}]}}}}')
            elif node.node_type == DAGNodeType.FAN_OUT.value:
                lines.append(f'  {node.node_id}[/"{node_label}<br/>[{node_type_label}]"\\]')
            elif node.node_type == DAGNodeType.FAN_IN.value:
                lines.append(f'  {node.node_id}[\\"{node_label}<br/>[{node_type_label}]"/]')
            elif node.node_type == DAGNodeType.DELAY.value:
                lines.append(f'  {node.node_id}(["{node_label}<br/>[{node_type_label}]"])')
            else:
                lines.append(f'  {node.node_id}["{node_label}<br/>[{node_type_label}]"]')

        # Edge definitions
        for edge in graph.edges:
            if not edge.enabled:
                continue
            if edge.source_node_id not in node_ids or edge.target_node_id not in node_ids:
                continue

            edge_style = "-->"
            edge_label = ""

            # Conditional edges
            if edge.condition and show_conditions:
                edge_label = f"|{self._escape_label(edge.condition)}|"
            elif edge.label and show_labels:
                edge_label = f"|{self._escape_label(edge.label)}|"

            # True/false branch styling
            if edge.label == "True" or edge.label == "true":
                edge_style = "-->"  # solid line for true
            elif edge.label == "False" or edge.label == "false":
                edge_style = "-.->"  # dotted line for false

            lines.append(f"  {edge.source_node_id}{edge_label}{edge_style}{edge.target_node_id}")

        # Style definitions
        lines.append("")
        for node_type, style in self.NODE_STYLES.items():
            lines.append(
                f"  classDef {node_type} fill:{style['fill']},stroke:#333,stroke-width:2px,color:{style['color']}"
            )
        for node in graph.nodes:
            lines.append(f"  class {node.node_id} {node.node_type}")

        lines.append("```")
        return "\n".join(lines)

    def to_graphviz(self, graph: DAGGraph, title: str = "") -> str:
        """
        Generate a Graphviz DOT format diagram.

        Args:
            graph: The DAG graph to visualize
            title: Optional diagram title

        Returns:
            Graphviz DOT syntax string
        """
        lines = ["digraph DAG {", '  rankdir=TD;', '  splines=ortho;']
        if title:
            lines.append(f'  label="{title}";')
            lines.append('  labelloc=t;')
            lines.append('  fontsize=20;')

        # Node definitions
        for node in graph.nodes:
            style = self.NODE_STYLES.get(node.node_type, {"shape": "box", "fill": "#9E9E9E", "color": "#fff"})
            shape_map = {
                "circle": "circle", "rect": "box", "diamond": "diamond",
                "hexagon": "hexagon", "stadium": "oval", "subroutine": "box3d",
                "trapezoid": "trapezium", "inv_trapezoid": "invtrapezium",
            }
            shape = shape_map.get(style["shape"], "box")
            label = f"{node.name or node.node_id[:8]}\\n[{node.node_type}]"
            lines.append(
                f'  {node.node_id} [shape={shape}, label="{label}", '
                f'style=filled, fillcolor="{style["fill"]}", fontcolor="{style["color"]}"];'
            )

        # Edge definitions
        for edge in graph.edges:
            if not edge.enabled:
                continue
            attrs = []
            if edge.label:
                attrs.append(f'label="{edge.label}"')
            if edge.condition:
                attrs.append(f'xlabel="{edge.condition}"')
            if edge.label in ("False", "false"):
                attrs.append('style=dashed')
            attr_str = f' [{", ".join(attrs)}]' if attrs else ""
            lines.append(f"  {edge.source_node_id} -> {edge.target_node_id}{attr_str};")

        lines.append("}")
        return "\n".join(lines)

    def to_ascii(self, graph: DAGGraph) -> str:
        """
        Generate a simple ASCII text representation of the DAG.

        Args:
            graph: The DAG graph to visualize

        Returns:
            ASCII art string
        """
        lines = [f"DAG: {graph.name or graph.graph_id}", "=" * 50]

        try:
            levels = graph.get_levels()
        except ValueError:
            levels = [[graph.nodes[0]]] if graph.nodes else []

        for level_idx, level in enumerate(levels):
            level_label = f"Level {level_idx + 1}"
            lines.append(f"\n{level_label}:")
            lines.append("  " + "  |  ".join(
                f"[{n.name or n.node_id[:8]}] ({n.node_type})" for n in level
            ))

            # Show edges from this level to next
            if level_idx < len(levels) - 1:
                next_level_ids = {n.node_id for n in levels[level_idx + 1]}
                for node in level:
                    for edge in graph.get_outgoing_edges(node.node_id):
                        if edge.target_node_id in next_level_ids:
                            condition = f" [{edge.condition}]" if edge.condition else ""
                            lines.append(f"    {node.name or node.node_id[:8]} --> {edge.target_node_id[:8]}{condition}")

        lines.append(f"\n{'=' * 50}")
        lines.append(f"Nodes: {len(graph.nodes)}, Edges: {len(graph.edges)}")
        return "\n".join(lines)

    def to_dict(self, graph: DAGGraph) -> Dict[str, Any]:
        """
        Generate all visualization formats as a dictionary.

        Returns:
            Dict with 'mermaid', 'graphviz', 'ascii', and 'stats' keys
        """
        return {
            "mermaid": self.to_mermaid(graph),
            "graphviz": self.to_graphviz(graph),
            "ascii": self.to_ascii(graph),
            "stats": {
                "node_count": len(graph.nodes),
                "edge_count": len(graph.edges),
                "node_types": self._count_node_types(graph),
                "depth": len(graph.get_levels()) if graph.nodes else 0,
            },
        }

    def _escape_label(self, text: str) -> str:
        """Escape special characters in labels."""
        return text.replace('"', '\\"').replace("\n", "<br/>")

    def _count_node_types(self, graph: DAGGraph) -> Dict[str, int]:
        """Count nodes by type."""
        counts = {}
        for node in graph.nodes:
            counts[node.node_type] = counts.get(node.node_type, 0) + 1
        return counts


_visualizer: Optional[DAGVisualizer] = None


def get_dag_visualizer() -> DAGVisualizer:
    global _visualizer
    if _visualizer is None:
        _visualizer = DAGVisualizer()
    return _visualizer