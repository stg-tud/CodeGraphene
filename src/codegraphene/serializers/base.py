"""Base serializer interface for CodeGraphene."""

from abc import abstractmethod

from ..core import BaseComponent, CodeGraph


class BaseSerializer(BaseComponent):
    """Abstract base class for all graph serializers."""

    @abstractmethod
    def serialize(self, graph: CodeGraph) -> str:
        """Serialize *graph* into a string representation for an LLM.

        Args:
            graph: The :class:`CodeGraph` to serialize.

        Returns:
            A string encoding of the graph suitable for use in an LLM prompt.
        """

    def run(self, current_graph=None, **context):
        """Execute serialization and return the prompt text.

        Issue #10 keeps serializers on the same adapter as parsers/trimmers so
        the pipeline can chain them without special cases.
        """
        if current_graph is None:
            raise ValueError("BaseSerializer.run() requires a graph input.")
        return self.serialize(current_graph)

    def describe(self) -> dict:
        info = super().describe()
        info.update(
            {
                "input_type": "CodeGraph",
                "output_type": "str",
                "requires_context": [],
                "capabilities": ["write_text"],
            }
        )
        return info
