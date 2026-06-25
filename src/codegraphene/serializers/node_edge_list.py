"""Serializer that returns the graph as Python lists of nodes and edges."""
# test

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..core import CodeGraph, Edge, Node, NodeGranularity


NodeListMode = Literal["only_id", "compact", "all"]


@dataclass
class CompactNode:
    """Minimal node view: stable local id, label, code, and line number."""

    local_id: int
    label: str
    code: str | None
    line: int | None


class NodeEdgeListSerializer:
    """Serialize a :class:`CodeGraph` into Python lists of nodes and edges.

    Joern-assigned node ids are always remapped to sequential integers starting
    at 0. Nodes are first sorted by ``(line, column, joern_id)`` so that local
    ids follow source reading order — outer expressions before nested children
    within a line. Edges reference these local ids, never the original Joern ids.

    Args:
        mode: Shape of the returned node list.
            - ``"only_id"`` → ``list[int]`` of local ids.
            - ``"compact"`` → ``list[CompactNode]`` (local_id, label, code, line).
            - ``"all"`` (default) → ``list[Node]`` with full properties; ``id``
              is the local id rendered as a string (to satisfy ``Node.id: str``).
        granularity: Used to extract code and line number in ``"compact"`` mode
            and as the line source for the sort key. Defaults to
            ``NodeGranularity.LINE``.
    """

    _NO_LINE = 10**9  # sentinel: nodes without a line sort after all line-numbered nodes

    def __init__(
        self,
        mode: NodeListMode = "all",
        granularity: NodeGranularity = NodeGranularity.LINE,
    ) -> None:
        self.mode = mode
        self.granularity = granularity

    def _sort_key(self, node: Node) -> tuple[int, int, str]:
        line = self.granularity.extract_line_number(node.properties)
        col_raw = node.properties.get("COLUMN_NUMBER")
        column = int(col_raw) if col_raw is not None else -1
        return (line if line is not None else self._NO_LINE, column, node.id)

    def serialize(
        self, graph: CodeGraph
    ) -> tuple[list[Node] | list[CompactNode] | list[int], list[Edge]]:
        joern_nodes = sorted(graph.get_nodes(), key=self._sort_key)
        id_map: dict[str, int] = {n.id: i for i, n in enumerate(joern_nodes)}

        nodes: list[Node] | list[CompactNode] | list[int]
        if self.mode == "only_id":
            nodes = list(id_map.values())
        elif self.mode == "compact":
            nodes = [
                CompactNode(
                    local_id=id_map[n.id],
                    label=n.label,
                    code=self.granularity.extract_code(n.properties),
                    line=self.granularity.extract_line_number(n.properties),
                )
                for n in joern_nodes
            ]
        else:  # "all"
            nodes = [
                Node(id=str(id_map[n.id]), label=n.label, properties=n.properties)
                for n in joern_nodes
            ]

        edges = [
            Edge(
                source=str(id_map[u]),
                target=str(id_map[v]),
                label=data.get("label", "CONNECTS_TO"),
            )
            for u, v, data in graph.nx_graph.edges(data=True)
        ]
        return nodes, edges
