"""GraphPipeline: orchestrates parse → trim → serialize."""

from .parsers.base import BaseParser
from .parsers.joern import JoernParser
from .trimmers.base import BaseTrimmer
from .serializers.base import BaseSerializer


class GraphPipeline:
    """Strings together a parser, trimmer, and serializer into a single pipeline.

    Args:
        parser:     A :class:`BaseParser` implementation for building the graph.
        trimmer:    A :class:`BaseTrimmer` implementation for reducing the graph.
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

    def run(self, file_path: str, target: str | int) -> str:
        """Execute the full pipeline on *file_path*.

        Args:
            file_path: Path to the input file to parse.
            target:    Identifies the focal node for trimming. Pass an ``int``
                       to match by line number, or a ``str`` to match by label
                       (e.g. a method name or file name), depending on the
                       configured granularity.

        Returns:
            The serialized string representation of the trimmed graph.
        """
        print(f"[Pipeline] Parsing {file_path}...")
        full_graph = self.parser.build_graph(file_path)

        granularity = self._get_granularity()
        target_nodes = granularity.find_target_nodes(full_graph, target)
        if not target_nodes:
            raise ValueError(
                f"No nodes found matching target {target!r} "
                f"under granularity {granularity!r}"
            )

        center_node_id = target_nodes[0].id
        print(f"[Pipeline] Trimming graph around {target!r} (Node {center_node_id})...")

        trimmed_graph = self.trimmer.trim(full_graph, center_node_id)
        print(
            f"[Pipeline] Trimmed from {full_graph.nx_graph.number_of_nodes()} "
            f"to {trimmed_graph.nx_graph.number_of_nodes()} nodes."
        )

        print("[Pipeline] Serializing subgraph...")
        return self.serializer.serialize(trimmed_graph)

    def _get_granularity(self):
        """Extract the granularity from the parser if available, else return the LINE default."""
        from .core import NodeGranularity
        if isinstance(self.parser, JoernParser):
            return self.parser.granularity
        return NodeGranularity.LINE