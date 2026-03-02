"""Base trimmer interface for CodeGraphene."""

from abc import ABC, abstractmethod

from ..core import CodeGraph


class BaseTrimmer(ABC):
    """Abstract base class for all graph trimmers."""

    @abstractmethod
    def trim(self, graph: CodeGraph, target_node_id: str) -> CodeGraph:
        """Return a trimmed subgraph focused on *target_node_id*.

        Args:
            graph: The full :class:`CodeGraph` to trim.
            target_node_id: The ID of the node to focus on.

        Returns:
            A new :class:`CodeGraph` representing the trimmed subgraph.
        """
