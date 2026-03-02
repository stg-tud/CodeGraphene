"""Text-based serializers for CodeGraphene."""

from .base import BaseSerializer
from ..core import CodeGraph


class CodeReconstructionSerializer(BaseSerializer):
    """Serializes a :class:`CodeGraph` by reconstructing source code lines.

    Nodes are sorted by line number and their ``code`` attributes are joined
    to produce a linearized source representation.
    """

    def serialize(self, graph: CodeGraph) -> str:
        """Reconstruct source code from the graph's nodes.

        Args:
            graph: The :class:`CodeGraph` to serialize.

        Returns:
            A newline-separated string of code lines, ordered by line number.
        """
        nodes = sorted(graph.get_nodes(), key=lambda n: n.line_number)
        return "\n".join(node.code for node in nodes)


class TextualGraphSerializer(BaseSerializer):
    """Serializes a :class:`CodeGraph` as a human-readable edge list.

    Each edge is represented as ``source_code --[label]--> target_code``.
    """

    def serialize(self, graph: CodeGraph) -> str:
        """Produce a textual edge-list representation of the graph.

        Args:
            graph: The :class:`CodeGraph` to serialize.

        Returns:
            A newline-separated string where each line describes one edge.
        """
        lines = []
        node_data = dict(graph.nx_graph.nodes(data=True))
        for u, v, data in graph.nx_graph.edges(data=True):
            src_code = node_data.get(u, {}).get("code", u)
            tgt_code = node_data.get(v, {}).get("code", v)
            label = data.get("label", "")
            lines.append(f"{src_code} --[{label}]--> {tgt_code}")
        return "\n".join(lines)
