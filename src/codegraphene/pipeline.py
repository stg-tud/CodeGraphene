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

    def run(self, input_path: str, target_node_id: str) -> str:
        """Execute the full pipeline on *input_path*.

        Args:
            input_path: Path to the input file to parse.
            target_node_id: The ID of the focal node for trimming.

        Returns:
            The serialized string representation of the trimmed graph.
        """
        graph = self.parser.build_graph(input_path)
        trimmed = self.trimmer.trim(graph, target_node_id)
        return self.serializer.serialize(trimmed)
