"""Tests for ProgramSlicer (issue #3)."""

import pytest

from codegraphene.core import CodeGraph, Edge, Node
from codegraphene.trimmers.slicer import ProgramSlicer


def _make_flow_graph() -> CodeGraph:
    """A tiny synthetic CPG mimicking a param -> use -> sink data/control flow.

    param(n) --REACHING_DEF--> cond(i<n) --CDG--> body(dst[i]=src[i]) --REACHING_DEF--> sink(ret)
    All nodes also share an unrelated AST edge chain, which a semantic-only
    slicer must ignore.
    """
    g = CodeGraph()
    g.add_node(Node(id="param", label="METHOD_PARAMETER_IN", properties={"LINE_NUMBER": "1", "CODE": "int n"}))
    g.add_node(Node(id="cond", label="CALL", properties={"LINE_NUMBER": "2", "CODE": "i<n"}))
    g.add_node(Node(id="body", label="CALL", properties={"LINE_NUMBER": "3", "CODE": "dst[i]=src[i]"}))
    g.add_node(Node(id="sink", label="METHOD_RETURN", properties={"LINE_NUMBER": "4", "CODE": "RET"}))
    g.add_node(Node(id="unrelated", label="COMMENT", properties={"LINE_NUMBER": "3", "CODE": "# noise"}))

    g.add_edge(Edge(source="param", target="cond", label="REACHING_DEF"))
    g.add_edge(Edge(source="cond", target="body", label="CDG"))
    g.add_edge(Edge(source="body", target="sink", label="REACHING_DEF"))
    # AST edge on the same line as "body" -- should only appear via expand_to_full_lines
    g.add_edge(Edge(source="body", target="unrelated", label="AST"))
    return g


class TestProgramSlicer:
    def test_missing_target_raises(self):
        slicer = ProgramSlicer()
        with pytest.raises(ValueError):
            slicer.trim(_make_flow_graph(), "does-not-exist")

    def test_forward_slice_follows_semantic_edges_only(self):
        graph = _make_flow_graph()
        result = ProgramSlicer(direction="forward").trim(graph, "param")
        ids = {n.id for n in result.get_nodes()}
        assert ids == {"param", "cond", "body", "sink"}
        assert "unrelated" not in ids  # only reachable via AST, not REACHING_DEF/CDG

    def test_backward_slice_follows_semantic_edges_only(self):
        graph = _make_flow_graph()
        result = ProgramSlicer(direction="backward").trim(graph, "sink")
        ids = {n.id for n in result.get_nodes()}
        assert ids == {"param", "cond", "body", "sink"}

    def test_both_directions_from_middle_node(self):
        graph = _make_flow_graph()
        result = ProgramSlicer(direction="both").trim(graph, "cond")
        ids = {n.id for n in result.get_nodes()}
        assert ids == {"param", "cond", "body", "sink"}

    def test_isolated_target_with_no_semantic_edges_returns_target_alone(self):
        graph = _make_flow_graph()
        result = ProgramSlicer(direction="both").trim(graph, "unrelated")
        assert {n.id for n in result.get_nodes()} == {"unrelated"}

    def test_expand_to_full_lines_pulls_in_same_line_nodes(self):
        graph = _make_flow_graph()
        result = ProgramSlicer(direction="forward", expand_to_full_lines=True).trim(graph, "param")
        ids = {n.id for n in result.get_nodes()}
        # "unrelated" shares line 3 with "body", which is in the slice
        assert "unrelated" in ids

    def test_custom_edge_types_restrict_traversal(self):
        graph = _make_flow_graph()
        # Only REACHING_DEF: cannot cross the CDG edge from cond to body
        result = ProgramSlicer(direction="forward", edge_types=["REACHING_DEF"]).trim(graph, "param")
        ids = {n.id for n in result.get_nodes()}
        assert ids == {"param", "cond"}

    def test_source_code_and_path_are_propagated(self):
        graph = _make_flow_graph()
        graph.source_code = "void copy(...) { ... }"
        graph.source_path = "copy.c"
        result = ProgramSlicer().trim(graph, "param")
        assert result.source_code == graph.source_code
        assert result.source_path == graph.source_path
