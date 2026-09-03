"""K-hop neighbourhood trimmer for CodeGraphene."""

import networkx as nx

from typing import List, Optional

from codegraphene.trimmers.base import BaseTrimmer
from codegraphene.core import CodeGraph, Edge, Node


class KHopTrimmer(BaseTrimmer):
    """Trims a :class:`CodeGraph` to the k-hop neighborhood of a target node.

    Args:
        hops: Number of hops to include around the target node.
    """

    def __init__(self, hops: int = 2, edge_types: Optional[List[str]] = None) -> None:
        self.hops = hops
        self.edge_types = edge_types

    def trim(self, graph: CodeGraph, target_node_id: str) -> CodeGraph:
        """Return the k-hop subgraph centred on *target_node_id*."""

        nx_graph = graph.nx_graph
        if target_node_id not in nx_graph:
            raise ValueError(f"Target node {target_node_id} not found in graph.")

        if self.edge_types is not None:

            def is_valid_edge(u, v, k):
                return nx_graph[u][v][k].get("label") in self.edge_types

            search_view = nx.subgraph_view(nx_graph, filter_edge=is_valid_edge)
        else:
            search_view = nx_graph

        if target_node_id not in search_view:
            return CodeGraph(source_code=graph.source_code, source_path=graph.source_path)

        ego = nx.ego_graph(search_view, target_node_id, radius=self.hops, undirected=True)

        trimmed_graph = CodeGraph(source_code=graph.source_code, source_path=graph.source_path)

        for _, data in ego.nodes(data=True):
            trimmed_graph.add_node(Node(**data))

        for u, v, _, data in ego.edges(keys=True, data=True):
            trimmed_graph.add_edge(
                Edge(source=u, target=v, label=data.get("label", ""))
            )

        return trimmed_graph

    def describe(self) -> dict:
        info = super().describe()
        info.update(
            {
                "name": "KHopTrimmer",
                "capabilities": ["graph_read"],
                "hops": self.hops,
            }
        )
        return info