"""Tests for NodeGranularity.find_target_nodes matcher types (issue #2)."""

import re

from codegraphene.core import CodeGraph, Edge, Node, NodeGranularity


def make_graph():
    cg = CodeGraph()
    cg.add_node(Node(id="1", label="CALL", code="requests.get(url)", line_number=1))
    cg.add_node(Node(id="2", label="CALL", code="requests.post(url)", line_number=2))
    cg.add_node(Node(id="3", label="IDENTIFIER", code="url", line_number=2))
    cg.add_edge(Edge(source="1", target="3", label="AST"))
    return cg


def test_int_matches_by_line_number():
    graph = make_graph()
    matches = NodeGranularity.LINE.find_target_nodes(graph, 2)
    assert {n.id for n in matches} == {"2", "3"}


def test_str_matches_exact_label():
    graph = make_graph()
    matches = NodeGranularity.LINE.find_target_nodes(graph, "IDENTIFIER")
    assert {n.id for n in matches} == {"3"}


def test_regex_pattern_matches_against_code():
    graph = make_graph()
    pattern = re.compile(r"requests\.get")
    matches = NodeGranularity.LINE.find_target_nodes(graph, pattern)
    assert {n.id for n in matches} == {"1"}


def test_regex_pattern_matches_against_label():
    graph = make_graph()
    pattern = re.compile(r"^CALL$")
    matches = NodeGranularity.LINE.find_target_nodes(graph, pattern)
    assert {n.id for n in matches} == {"1", "2"}


def test_callable_predicate():
    graph = make_graph()
    matches = NodeGranularity.LINE.find_target_nodes(
        graph, lambda node: node.label == "CALL" and "post" in (node.code or "")
    )
    assert {n.id for n in matches} == {"2"}
