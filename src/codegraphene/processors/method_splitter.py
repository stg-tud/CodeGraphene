"""Example Processor: Text -> Texts, splitting Python source per function/method.

Worked instance of the `Text => Texts` example from issue #14, using only the
standard library `ast` module (no new dependency).
"""

import ast
from typing import List

from .base import BaseProcessor


class MethodSplitterProcessor(BaseProcessor):
    """Splits a Python source file into one source snippet per function/method."""

    name = "MethodSplitterProcessor"

    def process(self, source_code: str) -> List[str]:
        tree = ast.parse(source_code)
        lines = source_code.splitlines(keepends=True)
        return [
            "".join(lines[node.lineno - 1 : node.end_lineno])
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

    def describe(self) -> dict:
        info = super().describe()
        info.update(
            {
                "name": self.name,
                "input_type": "Text/Code/Python",
                "output_type": "Texts/Code/Python",
            }
        )
        return info
