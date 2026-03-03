import networkx as nx
from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class Node:
    id: str
    label: str
    code: str
    line_number: int
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
