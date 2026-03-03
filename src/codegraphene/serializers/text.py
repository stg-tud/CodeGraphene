"""Text-based serializers for CodeGraphene."""

from .base import BaseSerializer
from ..core import CodeGraph


class CodeReconstructionSerializer(BaseSerializer):
    def serialize(self, graph: CodeGraph) -> str:
        """
        Reconstructs the source code sequentially from the nodes in the graph.
        """
        lines: dict[int, str] = {}
        for node in graph.get_nodes():
            if node.line_number > 0 and node.code and node.code != "<empty>":
                # Joern often creates multiple nodes for a single line (e.g., the whole statement, 
                # plus individual variables). We take the longest code string per line to capture the full statement.
                if node.line_number not in lines or len(node.code) > len(lines[node.line_number]):
                    lines[node.line_number] = node.code
        
        sorted_line_numbers = sorted(lines.keys())
        
        reconstructed_code =[]
        for line_num in sorted_line_numbers:
            reconstructed_code.append(f"Line {line_num}: {lines[line_num]}")
            
        return "\n".join(reconstructed_code)

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
