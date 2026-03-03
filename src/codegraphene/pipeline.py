"""GraphPipeline: orchestrates parse → trim → serialize."""

from .parsers.base import BaseParser
from .trimmers.base import BaseTrimmer
from .serializers.base import BaseSerializer


class GraphPipeline:
    """Strings together a parser, trimmer, and serializer into a single pipeline.

    Args:
        parser: A :class:`BaseParser` implementation for building the graph.
        trimmer: A :class:`BaseTrimmer` implementation for reducing the graph.
        serializer: A :class:`BaseSerializer` implementation for encoding the graph.
    """

    def __init__(
        self,
        parser: BaseParser,
        trimmer: BaseTrimmer,
        serializer: BaseSerializer,
    ) -> None:
        self.parser = parser
        self.trimmer = trimmer
        self.serializer = serializer

    def run(self, file_path: str, target_line: int) -> str:
        """Execute the full pipeline on *file_path*.

        Args:
            file_path: Path to the input file to parse.
            target_line: The line number of the focal node for trimming.

        Returns:
            The serialized string representation of the trimmed graph.
        """
        print(f"[Pipeline] Parsing {file_path}...")
        full_graph = self.parser.build_graph(file_path)
        
        target_nodes = full_graph.get_nodes_by_line(target_line)
        if not target_nodes:
            raise ValueError(f"No code nodes found on line {target_line}")
        
        center_node_id = target_nodes[0].id
        print(f"[Pipeline] Trimming graph around line {target_line} (Node {center_node_id})...")
        
        trimmed_graph = self.trimmer.trim(full_graph, center_node_id)
        print(f"[Pipeline] Trimmed from {full_graph.nx_graph.number_of_nodes()} to {trimmed_graph.nx_graph.number_of_nodes()} nodes.")
        
        print("[Pipeline] Serializing subgraph...")
        result = self.serializer.serialize(trimmed_graph)
        
        return result
