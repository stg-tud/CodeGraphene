"""Base trimmer interface for CodeGraphene."""

from abc import abstractmethod

from ..core import BaseComponent, CodeGraph


class BaseTrimmer(BaseComponent):
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

    def run(self, current_graph=None, **context):
        """Execute the trim step using the shared pipeline context."""
        if current_graph is None:
            raise ValueError("BaseTrimmer.run() requires a graph input.")
        target_node_id = context.get("target_node_id")
        if target_node_id is None:
            raise ValueError("BaseTrimmer.run() requires 'target_node_id'.")
        return self.trim(current_graph, target_node_id)

    def describe(self) -> dict:
        info = super().describe()
        info.update(
            {
                "input_type": "CodeGraph",
                "output_type": "CodeGraph",
                "requires_context": ["target_node_id"],
                "capabilities": ["graph_read"],
            }
        )
        return info
