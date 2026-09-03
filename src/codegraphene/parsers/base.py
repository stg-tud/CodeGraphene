"""Base parser interface for CodeGraphene."""

from abc import abstractmethod

from ..core import BaseComponent, CodeGraph


class BaseParser(BaseComponent):
    """Abstract base class for all graph parsers."""

    @abstractmethod
    def build_graph(self, file_path: str) -> CodeGraph:
        """Parse a source artifact and return a :class:`CodeGraph`.

        Args:
            file_path: Path to the input file (e.g., a DOT export).

        Returns:
            A populated :class:`CodeGraph` instance.
        """

    def run(self, current_graph=None, **context):
        """Execute the parser and return a graph.

        The explicit file_path argument is part of the issue #10 contract: the
        pipeline should not need parser-specific entry points.
        """
        file_path = context.get("file_path")
        if not file_path:
            raise ValueError("BaseParser.run() requires 'file_path'.")
        return self.build_graph(file_path)

    def describe(self) -> dict:
        info = super().describe()
        info.update(
            {
                "input_type": "file_path",
                "output_type": "CodeGraph",
                "requires_context": ["file_path"],
                "capabilities": ["read_file"],
            }
        )
        return info
