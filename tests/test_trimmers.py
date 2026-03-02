"""Tests for the trimmers sub-package."""

import pytest

from codegraphene.core import CodeGraph, Node, Edge
from codegraphene.trimmers.base import BaseTrimmer
from codegraphene.trimmers.khop import KHopTrimmer


def _make_simple_graph() -> CodeGraph:
    """Return a small three-node graph for testing."""
    g = CodeGraph()
    for i, code in enumerate(["a = 1", "b = 2", "c = 3"], start=1):
        g.add_node(Node(id=str(i), label="ASSIGN", code=code, line_number=i))
    g.add_edge(Edge(source="1", target="2", label="CFG"))
    g.add_edge(Edge(source="2", target="3", label="CFG"))
    return g


class TestBaseTrimmer:
    def test_abstract_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            BaseTrimmer()  # type: ignore[abstract]


class TestKHopTrimmer:
    def test_instantiation(self):
        trimmer = KHopTrimmer(hops=2)
        assert trimmer.hops == 2

    def test_trim_returns_code_graph(self):
        trimmer = KHopTrimmer(hops=1)
        graph = _make_simple_graph()
        result = trimmer.trim(graph, target_node_id="1")
        assert isinstance(result, CodeGraph)

    def test_trim_currently_returns_original_graph(self):
        """KHopTrimmer is a stub; it should return the unmodified graph."""
        trimmer = KHopTrimmer(hops=1)
        graph = _make_simple_graph()
        result = trimmer.trim(graph, target_node_id="2")
        assert result is graph
