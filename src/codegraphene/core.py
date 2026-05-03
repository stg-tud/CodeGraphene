from __future__ import annotations
import networkx as nx
from dataclasses import dataclass, field
from typing import ClassVar, Dict, Any, List, Set


class NodeGranularity:
    """Defines which CPG node attributes are required, and which to use as the label."""
    LINE:   ClassVar[NodeGranularity]
    METHOD: ClassVar[NodeGranularity]
    FILE:   ClassVar[NodeGranularity]

    def __init__(
        self,
        required_attrs: Set[str],
        label_attr: str,
        code_attr: str,
        granularity_name: str,
        line_attr: str | None = None,
    ) -> None:
        self.required_attrs = frozenset(required_attrs)
        self.label_attr = label_attr
        self.code_attr = code_attr
        self.line_attr = line_attr  # None means granularity has no meaningful line ordering
        self.granularity_name = granularity_name

    def is_valid(self, data: dict) -> bool:
        return self.required_attrs.issubset(data.keys())

    def extract_label(self, data: dict) -> str:
        return data.get(self.label_attr, "UNKNOWN")

    def extract_code(self, properties: dict) -> str | None:
        return properties.get(self.code_attr)

    def extract_line_number(self, properties: dict) -> int | None:
        if self.line_attr is None:
            return None
        try:
            return int(properties[self.line_attr])
        except (KeyError, ValueError):
            return None
    
    def find_target_nodes(self, graph: CodeGraph, target: str | int) -> list[Node]:
        """Return nodes whose line number or label attribute matches *target*."""
        matches = []
        for node in graph.get_nodes():
            if self.line_attr is not None and isinstance(target, int):
                if self.extract_line_number(node.properties) == target:
                    matches.append(node)
            else:
                if node.label == str(target):
                    matches.append(node)
        return matches


NodeGranularity.LINE = NodeGranularity(
    required_attrs={"LINE_NUMBER", "CODE"},
    label_attr="label",
    code_attr="CODE",
    line_attr="LINE_NUMBER",
    granularity_name="LINE",
)
NodeGranularity.METHOD = NodeGranularity(
    required_attrs={"NAME", "FULL_NAME"},
    label_attr="NAME",
    code_attr="FULL_NAME",
    line_attr=None,
    granularity_name="METHOD",
)
NodeGranularity.FILE = NodeGranularity(
    required_attrs={"NAME"},
    label_attr="NAME",
    code_attr="NAME",
    line_attr=None,
    granularity_name="FILE",
)


@dataclass
class Node:
    id: str
    label: str
    properties: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Edge:
    source: str
    target: str
    label: str


class CodeGraph:
    def __init__(self):
        self.nx_graph = nx.MultiDiGraph()

    def add_node(self, node: Node):
        self.nx_graph.add_node(node.id, **node.__dict__)

    def add_edge(self, edge: Edge):
        self.nx_graph.add_edge(edge.source, edge.target, label=edge.label)

    def get_nodes(self) -> List[Node]:
        return [Node(**data) for _, data in self.nx_graph.nodes(data=True)]
        
    def get_nodes_by_line(self, line_number: int) -> List[Node]:
        return[Node(**data) for _, data in self.nx_graph.nodes(data=True) 
                if data.get('line_number') == line_number]

    def summary(self) -> str:
        return (
            f"CodeGraph with {self.nx_graph.number_of_nodes()} nodes "
            f"and {self.nx_graph.number_of_edges()} edges."
        )
