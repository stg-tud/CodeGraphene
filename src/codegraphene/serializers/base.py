"""Base serializer interface for CodeGraphene."""

from abc import ABC, abstractmethod

from ..core import CodeGraph


class BaseSerializer(ABC):
    """Abstract base class for all graph serializers."""

    @abstractmethod
    def serialize(self, graph: CodeGraph) -> str:
        """Serialize *graph* into a string representation for an LLM.

        Args:
            graph: The :class:`CodeGraph` to serialize.

        Returns:
            A string encoding of the graph suitable for use in an LLM prompt.
        """
