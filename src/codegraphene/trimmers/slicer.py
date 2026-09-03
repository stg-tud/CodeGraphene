"""ProgramSlicer: semantic backward/forward slicing over data/control dependencies.

Unlike KHopTrimmer (structural distance in the AST/CFG), ProgramSlicer
traces data (REACHING_DEF) and control (CDG) dependencies to isolate the
statements that actually influence -- or are influenced by -- a target
node, ignoring structurally nearby but semantically irrelevant code.

Designed to run on a graph parsed with NodeGranularity.RAW (the full,
unfiltered CPG). REACHING_DEF/CDG edges reach node types (METHOD,
METHOD_PARAMETER_IN/OUT, METHOD_RETURN, ...) that LINE/METHOD/FILE
granularity drop at parse time -- roughly a quarter of semantic edges in a
small test snippet, including every parameter-in/out edge. Running this
against a granularity-filtered graph will silently miss those paths.
"""

from __future__ import annotations

from typing import Literal, Optional, Sequence

import networkx as nx

from ..core import CodeGraph, Edge, Node
from .base import BaseTrimmer

Direction = Literal["backward", "forward", "both"]

DEFAULT_EDGE_TYPES = ("REACHING_DEF", "CDG")


class ProgramSlicer(BaseTrimmer):
    """Slice a CodeGraph to the semantic dependency closure of a target node.

    Args:
        direction: "backward" (what influences the target, via
            nx.ancestors), "forward" (what the target influences, via
            nx.descendants), or "both" (default).
        edge_types: Edge labels to traverse. Defaults to REACHING_DEF
            (data dependency) and CDG (control dependency).
        expand_to_full_lines: Data-dependency edges connect directly to
            IDENTIFIER-level nodes, so the raw slice is fragmented tokens
            rather than full statements. When True, every line number
            touched by the slice is expanded to include all nodes sharing
            that line from the original graph, so a serializer can output
            complete, readable statements.
    """

    def __init__(
        self,
        direction: Direction = "both",
        edge_types: Optional[Sequence[str]] = None,
        expand_to_full_lines: bool = False,
    ) -> None:
        self.direction = direction
        self.edge_types = tuple(edge_types) if edge_types is not None else DEFAULT_EDGE_TYPES
        self.expand_to_full_lines = expand_to_full_lines

    def trim(self, graph: CodeGraph, target_node_id: str) -> CodeGraph:
        nx_graph = graph.nx_graph
        if target_node_id not in nx_graph:
            raise ValueError(f"Target node {target_node_id} not found in graph.")

        edge_types = self.edge_types

        def is_semantic_edge(u, v, k):
            return nx_graph[u][v][k].get("label") in edge_types

        semantic_view = nx.subgraph_view(nx_graph, filter_edge=is_semantic_edge)

        keep_ids: set[str] = {target_node_id}
        if target_node_id in semantic_view:
            if self.direction in ("backward", "both"):
                keep_ids |= nx.ancestors(semantic_view, target_node_id)
            if self.direction in ("forward", "both"):
                keep_ids |= nx.descendants(semantic_view, target_node_id)

        if self.expand_to_full_lines:
            keep_ids = self._expand_to_full_lines(nx_graph, keep_ids)

        return self._induced_subgraph(graph, keep_ids)

    def _expand_to_full_lines(self, nx_graph: nx.MultiDiGraph, node_ids: set[str]) -> set[str]:
        line_numbers = set()
        for nid in node_ids:
            line = nx_graph.nodes[nid].get("line_number")
            if line is not None:
                line_numbers.add(line)

        if not line_numbers:
            return node_ids

        expanded = set(node_ids)
        for nid, data in nx_graph.nodes(data=True):
            if data.get("line_number") in line_numbers:
                expanded.add(nid)
        return expanded

    def _induced_subgraph(self, graph: CodeGraph, node_ids: set[str]) -> CodeGraph:
        nx_graph = graph.nx_graph
        out = CodeGraph(source_code=graph.source_code, source_path=graph.source_path)
        for nid in node_ids:
            out.add_node(Node(**nx_graph.nodes[nid]))
        for u, v, data in nx_graph.edges(data=True):
            if u in node_ids and v in node_ids:
                out.add_edge(Edge(source=u, target=v, label=data.get("label", "")))
        return out

    def describe(self) -> dict:
        info = super().describe()
        info.update(
            {
                "name": "ProgramSlicer",
                "capabilities": ["graph_read"],
                "direction": self.direction,
                "edge_types": list(self.edge_types),
                "expand_to_full_lines": self.expand_to_full_lines,
            }
        )
        return info
