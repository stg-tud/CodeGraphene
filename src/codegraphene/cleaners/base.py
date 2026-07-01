"""Base cleaner interface for CodeGraphene."""

from abc import abstractmethod

from ..core import BaseComponent


class BaseCleaner(BaseComponent):
    """Base class for all cleaners.

    Runs before the parser, takes raw source text, returns cleaned text.
    One string in, one string out.
    """

    @abstractmethod
    def clean(self, source_code: str) -> str:
        """Return a cleaned version of *source_code*."""

    def run(self, current_graph=None, **context):
        """Run the cleaner. Looks for source text in this order:
        1. source_code in context
        2. current_graph if it's a string (i.e. a previous cleaner ran)
        3. reads from file_path if nothing else is available
        """
        source_code = context.get("source_code")

        if source_code is None and isinstance(current_graph, str):
            source_code = current_graph

        if source_code is None:
            file_path = context.get("file_path")
            if file_path is None:
                raise ValueError(
                    "BaseCleaner.run() requires 'source_code', a string "
                    "'current_graph', or 'file_path' in context."
                )
            with open(file_path, encoding="utf-8") as fh:
                source_code = fh.read()

        return self.clean(source_code)

    def describe(self) -> dict:
        info = super().describe()
        info.update(
            {
                "input_type": "str",
                "output_type": "str",
                "requires_context": [],
                "capabilities": ["read_text", "write_text"],
            }
        )
        return info
