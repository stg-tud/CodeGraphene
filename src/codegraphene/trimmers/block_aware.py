"""
BlockAwareTrimmer: wraps any trimmer and pads its output with the enclosing
C/C++ block boundaries so the resulting slice is brace-balanced.
"""

from __future__ import annotations

from typing import List, Optional, Set

from ..blocks import CodeBlock, analyze_c_code, smallest_enclosing_block
from ..core import CodeGraph, Node, NodeGranularity
from .base import BaseTrimmer

SYNTHETIC_LABEL = "SYNTHETIC_BLOCK_BOUNDARY"


class BlockAwareTrimmer(BaseTrimmer):
    """Wraps an inner trimmer; injects synthetic nodes for enclosing braces.

    For each line covered by a node in the inner trimmer's output, walks up
    the C block hierarchy and includes the start/end line of every
    enclosing block. Lines that have no existing graph node are filled by
    *synthetic* nodes (label=SYNTHETIC_BLOCK_BOUNDARY) carrying the source
    line text — so the existing CodeReconstructionSerializer can render
    them without modification.

    Requires the input graph to carry source code via ``CodeGraph.source_code``
    (JoernParser populates this automatically). If it's missing, the trimmer
    returns the inner result unmodified.

    Args:
        inner:         Trimmer to wrap (KHopTrimmer, TaintFlowTrimmer, ...).
        granularity:   Used to extract line numbers from existing nodes.
                       Defaults to NodeGranularity.LINE.
    """

    def __init__(
        self,
        inner: BaseTrimmer,
        granularity: NodeGranularity = NodeGranularity.LINE,
    ) -> None:
        self.inner = inner
        self.granularity = granularity

    def trim(self, graph: CodeGraph, target_node_id: str) -> CodeGraph:
        trimmed = self.inner.trim(graph, target_node_id)

        source = trimmed.source_code or graph.source_code
        if not source:
            return trimmed

        blocks = analyze_c_code(source)
        if not blocks:
            return trimmed

        covered_lines = self._covered_lines(trimmed)
        if not covered_lines:
            return trimmed

        brace_lines = self._enclosing_brace_lines(covered_lines, blocks)
        new_lines = brace_lines - covered_lines
        if not new_lines:
            return trimmed

        source_lines = source.splitlines()
        for ln in sorted(new_lines):
            if 1 <= ln <= len(source_lines):
                self._add_synthetic(trimmed, ln, source_lines[ln - 1])

        return trimmed

    # ------------------------------------------------------------------

    def _covered_lines(self, graph: CodeGraph) -> Set[int]:
        lines: Set[int] = set()
        for node in graph.get_nodes():
            ln = self.granularity.extract_line_number(node.properties)
            if ln is not None and ln >= 1:
                lines.add(ln)
        return lines

    def _enclosing_brace_lines(
        self,
        covered: Set[int],
        blocks: List[CodeBlock],
    ) -> Set[int]:
        out: Set[int] = set()
        for line in covered:
            cursor = line
            for _ in range(len(blocks) + 1):  # bounded climb
                enclosing = smallest_enclosing_block(cursor, blocks)
                if enclosing is None:
                    break
                out.add(enclosing.start_line)
                out.add(enclosing.end_line)
                cursor = enclosing.start_line - 1
                if cursor < 1:
                    break
        return out

    def _add_synthetic(self, graph: CodeGraph, line: int, code: str) -> None:
        node_id = f"synthetic:{line}"
        if node_id in graph.nx_graph:
            return
        node = Node(
            id=node_id,
            label=SYNTHETIC_LABEL,
            properties={
                "CODE": code,
                "LINE_NUMBER": str(line),
                "SYNTHETIC": True,
            },
        )
        graph.add_node(node)
