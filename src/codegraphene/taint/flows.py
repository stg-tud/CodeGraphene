"""
Dataclasses representing taint flows over a CPG.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class TaintFlowElement:
    """A single node on a taint flow path."""

    node_id: str
    line_number: Optional[int]
    line_code: str = ""


@dataclass
class TaintFlow:
    """A complete taint flow path from a source node to a sink node."""

    elements: List[TaintFlowElement]

    @property
    def source(self) -> Optional[TaintFlowElement]:
        return self.elements[0] if self.elements else None

    @property
    def sink(self) -> Optional[TaintFlowElement]:
        return self.elements[-1] if self.elements else None

    @property
    def line_numbers(self) -> List[int]:
        return [e.line_number for e in self.elements if e.line_number is not None]

    @property
    def node_ids(self) -> List[str]:
        return [e.node_id for e in self.elements]

    def __str__(self) -> str:
        return "\n".join(
            f"  L{e.line_number}: {e.line_code}"
            for e in self.elements
            if e.line_number is not None
        )
