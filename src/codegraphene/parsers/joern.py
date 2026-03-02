"""Joern DOT-file parser for CodeGraphene."""

import networkx as nx

from .base import BaseParser
from ..core import CodeGraph, Node, Edge


class JoernParser(BaseParser):
    """Parser that reads a Joern-exported DOT file into a :class:`CodeGraph`."""

    def build_graph(self, dot_file_path: str) -> CodeGraph:
        """Build a :class:`CodeGraph` from a Joern DOT export.

        Args:
            dot_file_path: Path to the ``.dot`` file produced by Joern.

        Returns:
            A :class:`CodeGraph` containing only nodes that have both
            ``LINE_NUMBER`` and ``CODE`` attributes, along with the
            edges connecting those nodes.
        """
        raw_nx_graph = nx.drawing.nx_pydot.read_dot(dot_file_path)
        code_graph = CodeGraph()

        for node_id, data in raw_nx_graph.nodes(data=True):
            clean_data = {
                k: v.strip('"') if isinstance(v, str) else v
                for k, v in data.items()
            }
            if "LINE_NUMBER" in clean_data and "CODE" in clean_data:
                try:
                    line_num = int(clean_data["LINE_NUMBER"])
                except ValueError:
                    line_num = -1

                node = Node(
                    id=node_id,
                    label=clean_data.get("label", "UNKNOWN"),
                    code=clean_data["CODE"],
                    line_number=line_num,
                    properties=clean_data,
                )
                code_graph.add_node(node)

        valid_node_ids = set(code_graph.nx_graph.nodes())

        for u, v, data in raw_nx_graph.edges(data=True):
            if u in valid_node_ids and v in valid_node_ids:
                clean_label = data.get("label", '""').strip('"')
                edge = Edge(source=u, target=v, label=clean_label)
                code_graph.add_edge(edge)

        return code_graph
