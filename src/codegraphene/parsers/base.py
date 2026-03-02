"""Base parser interface for CodeGraphene."""

from abc import ABC, abstractmethod

from ..core import CodeGraph


class BaseParser(ABC):
    """Abstract base class for all graph parsers."""

    @abstractmethod
    def build_graph(self, file_path: str) -> CodeGraph:
        """Parse a source artifact and return a :class:`CodeGraph`.

        Args:
            file_path: Path to the input file (e.g., a DOT export).

        Returns:
            A populated :class:`CodeGraph` instance.
        """
