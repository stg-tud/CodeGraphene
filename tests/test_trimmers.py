"""Tests for the trimmers sub-package."""

import pytest

from codegraphene.core import CodeGraph, Node, Edge
from codegraphene.trimmers.base import BaseTrimmer
from codegraphene.trimmers.khop import KHopTrimmer


def _make_simple_graph() -> CodeGraph:
    """Return a small three-node graph for testing."""
    g = CodeGraph()
    for i, code in enumerate(["a = 1", "b = 2", "c = 3"], start=1):
        g.add_node(
            Node(
                id=str(i),
                label="ASSIGN",
                properties={"LINE_NUMBER": str(i), "CODE": code},
            )
        )
    g.add_edge(Edge(source="1", target="2", label="CFG"))
    g.add_edge(Edge(source="2", target="3", label="CFG"))
    return g


class TestBaseTrimmer:
    def test_abstract_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            BaseTrimmer()  # type: ignore[abstract]


class TestKHopTrimmer:
    """Unit tests for KHopTrimmer."""

    # Test that KHopTrimmer can be instantiated with different hop counts
    def test_instantiation(self):
        trimmer = KHopTrimmer(hops=2)
        assert trimmer.hops == 2

    # Test that trim returns a CodeGraph instance
    def test_trim_returns_code_graph(self):
        trimmer = KHopTrimmer(hops=1)
        graph = _make_simple_graph()
        result = trimmer.trim(graph, target_node_id="1")
        assert isinstance(result, CodeGraph)

    # Test that trim returns the original graph since KHopTrimmer is currently a stub
    def test_trim_currently_returns_original_graph(self):
        """KHopTrimmer is a stub; it should return the unmodified graph."""
        trimmer = KHopTrimmer(hops=1)
        graph = _make_simple_graph()
        result = trimmer.trim(graph, target_node_id="2")
        assert result is graph

    # Test trim raises ValueError if target node is not in the graph
    def test_trim_raises_if_target_node_not_in_graph(self):
        trimmer = KHopTrimmer(hops=1)
        graph = _make_simple_graph()
        with pytest.raises(ValueError):
            trimmer.trim(graph, target_node_id="999")

    # Test trim returns empty graph if edge_types filter excludes all edges
    def test_trim_returns_empty_graph_if_edge_types_exclude_all(self):
        trimmer = KHopTrimmer(hops=1, edge_types=["NON_EXISTENT_EDGE_TYPE"])
        graph = _make_simple_graph()
        result = trimmer.trim(graph, target_node_id="1")
        assert isinstance(result, CodeGraph)
        assert result.nx_graph.number_of_nodes() == 0
        assert result.nx_graph.number_of_edges() == 0

    # Test trim returns correct subgraph for 1-hop neighborhood
    def test_trim_returns_correct_subgraph_for_1_hop(self):
        trimmer = KHopTrimmer(hops=1)
        graph = _make_simple_graph()
        result = trimmer.trim(graph, target_node_id="2")
        assert isinstance(result, CodeGraph)
        assert result.nx_graph.number_of_nodes() == 3  # Nodes 1, 2, 3
        assert result.nx_graph.number_of_edges() == 2  # Edges 1->2 and 2->3
