"""Tests for the BlockAwareTrimmer."""

import pytest

from codegraphene.core import CodeGraph, Edge, Node
from codegraphene.serializers.text import CodeReconstructionSerializer
from codegraphene.trimmers.base import BaseTrimmer
from codegraphene.trimmers.block_aware import (
    SYNTHETIC_LABEL,
    BlockAwareTrimmer,
)


SOURCE = """\
int foo(int x) {
    if (x > 0) {
        return x;
    }
    return -x;
}
"""


def _node(node_id: str, line: int, code: str) -> Node:
    return Node(
        id=node_id,
        label="CALL",
        properties={"CODE": code, "LINE_NUMBER": str(line)},
    )


def _graph_with_only_line_3() -> CodeGraph:
    """Mimics a trimmer output that kept only `return x;` on line 3."""
    g = CodeGraph(source_code=SOURCE, source_path="foo.c")
    g.add_node(_node("n3", 3, "return x"))
    return g


class _PassthroughTrimmer(BaseTrimmer):
    """Trimmer stub for tests: returns the input graph unchanged."""

    def trim(self, graph: CodeGraph, target_node_id: str) -> CodeGraph:
        return graph


class TestBlockAwareTrimmer:
    def test_adds_synthetic_brace_lines_around_covered_line(self):
        g = _graph_with_only_line_3()
        trimmer = BlockAwareTrimmer(inner=_PassthroughTrimmer())
        out = trimmer.trim(g, target_node_id="n3")

        # Covered line 3 sits inside the if (lines 2..4), which sits inside
        # the function (lines 1..6). Brace lines added: 1, 2, 4, 6.
        line_numbers = {
            int(data["properties"].get("LINE_NUMBER"))
            for _, data in out.nx_graph.nodes(data=True)
            if data["properties"].get("LINE_NUMBER")
        }
        assert {1, 2, 3, 4, 6}.issubset(line_numbers)

    def test_synthetic_nodes_have_marker(self):
        g = _graph_with_only_line_3()
        trimmer = BlockAwareTrimmer(inner=_PassthroughTrimmer())
        out = trimmer.trim(g, target_node_id="n3")

        synthetics = [
            n for n in out.get_nodes()
            if n.label == SYNTHETIC_LABEL
        ]
        assert synthetics, "expected synthetic brace nodes"
        assert all(n.properties.get("SYNTHETIC") is True for n in synthetics)

    def test_serializer_renders_brace_lines(self):
        g = _graph_with_only_line_3()
        trimmer = BlockAwareTrimmer(inner=_PassthroughTrimmer())
        out = trimmer.trim(g, target_node_id="n3")

        rendered = CodeReconstructionSerializer().serialize(out)
        # The serializer prints "Line N: <code>" — check brace lines made it.
        assert "Line 1:" in rendered  # function header
        assert "Line 6:" in rendered  # closing brace of function
        assert "Line 3:" in rendered  # original covered line

    def test_no_source_returns_inner_result_unchanged(self):
        g = CodeGraph()  # no source_code
        g.add_node(_node("n3", 3, "return x"))
        trimmer = BlockAwareTrimmer(inner=_PassthroughTrimmer())
        out = trimmer.trim(g, target_node_id="n3")
        # No synthetic nodes when source is missing.
        assert not any(n.label == SYNTHETIC_LABEL for n in out.get_nodes())

    def test_does_not_overwrite_existing_lines(self):
        g = _graph_with_only_line_3()
        # Pretend the inner trimmer also kept line 1 (the function header).
        g.add_node(_node("n1", 1, "int foo(int x) {"))

        trimmer = BlockAwareTrimmer(inner=_PassthroughTrimmer())
        out = trimmer.trim(g, target_node_id="n3")

        # Line 1 should still be the real node (not a synthetic).
        line_1_labels = [
            data["label"]
            for _, data in out.nx_graph.nodes(data=True)
            if data["properties"].get("LINE_NUMBER") == "1"
        ]
        assert "CALL" in line_1_labels
        assert SYNTHETIC_LABEL not in line_1_labels
