"""Text-based serializers for CodeGraphene."""

from .base import BaseSerializer
from ..core import CodeGraph, NodeGranularity


# class CodeReconstructionSerializer(BaseSerializer):
#     def serialize(self, graph: CodeGraph) -> str:
#         """
#         Reconstructs the source code sequentially from the nodes in the graph.
#         """
#         lines: dict[int, str] = {}
#         for node in graph.get_nodes():
#             if node.line_number > 0 and node.code and node.code != "<empty>":
#                 # Joern often creates multiple nodes for a single line (e.g., the whole statement, 
#                 # plus individual variables). We take the longest code string per line to capture the full statement.
#                 if node.line_number not in lines or len(node.code) > len(lines[node.line_number]):
#                     lines[node.line_number] = node.code
        
#         sorted_line_numbers = sorted(lines.keys())
        
#         reconstructed_code =[]
#         for line_num in sorted_line_numbers:
#             reconstructed_code.append(f"Line {line_num}: {lines[line_num]}")
            
#         return "\n".join(reconstructed_code)

class CodeReconstructionSerializer(BaseSerializer):
    def __init__(self, granularity: NodeGranularity = NodeGranularity.LINE) -> None:
        """
        :param granularity: Controls which node properties are used to extract
                            code content and line ordering. Defaults to NodeGranularity.LINE.
        """
        self.granularity = granularity

    def serialize(self, graph: CodeGraph) -> str:
        """Reconstructs source code sequentially from the nodes in the graph."""
        if self.granularity.line_attr is None:
            return self._serialize_unordered(graph)
        return self._serialize_by_line(graph)

    def _serialize_by_line(self, graph: CodeGraph) -> str:
        """Serialize nodes ordered by line number, deduplicating by longest code per line."""
        lines: dict[int, str] = {}

        for node in graph.get_nodes():
            line_number = self.granularity.extract_line_number(node.properties)
            code = self.granularity.extract_code(node.properties)

            if line_number is None or line_number <= 0:
                continue
            if not code or code == "<empty>":
                continue
            if line_number not in lines or len(code) > len(lines[line_number]):
                lines[line_number] = code

        return "\n".join(
            f"Line {ln}: {lines[ln]}" for ln in sorted(lines.keys())
        )

    def _serialize_unordered(self, graph: CodeGraph) -> str:
        """Serialize nodes without line ordering, for granularities without line info."""
        entries = []
        for node in graph.get_nodes():
            code = self.granularity.extract_code(node.properties)
            if code and code != "<empty>":
                entries.append(code)
        return "\n".join(entries)


class TextualGraphSerializer(BaseSerializer):
    def serialize(self, graph: CodeGraph) -> str:
        """
        Outputs a simple text summary of the edges for the LLM to read.
        """
        output =[]
        for u, v, data in graph.nx_graph.edges(data=True):
            edge_type = data.get("label", "CONNECTS_TO")
            output.append(f"Node {u} {edge_type} Node {v}")
        return "\n".join(output)
