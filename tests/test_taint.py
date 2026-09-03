"""Tests for the taint sub-package and TaintFlowTrimmer."""

import pytest

from codegraphene.core import CodeGraph, Edge, Node
from codegraphene.taint import (
    CWETemplate,
    TaintExtractor,
    TaintFlow,
    TaintFlowElement,
    get_template,
    supported_cwes,
)
from codegraphene.trimmers.taint_flow import TaintFlowTrimmer


def _cpg_node(node_id: str, label: str, code: str, line: int, name: str = "") -> Node:
    props = {"CODE": code, "LINE_NUMBER": str(line)}
    if name:
        props["NAME"] = name
    return Node(id=node_id, label=label, properties=props)


def _build_buffer_overflow_graph() -> CodeGraph:
    """Synthetic mini-CPG: parameter `dst` flows via an intermediate identifier
    into a memcpy call on line 3. The 'noise' node has no DDG edge into the
    sink, so it should not appear on any flow.
    """
    g = CodeGraph()
    g.add_node(_cpg_node("p1", "METHOD_PARAMETER_IN", "char *dst", 1, name="dst"))
    g.add_node(_cpg_node("i1", "IDENTIFIER", "dst", 2, name="dst"))
    g.add_node(_cpg_node("c1", "CALL", "memcpy(dst, src, n)", 3, name="memcpy"))
    g.add_node(_cpg_node("n1", "IDENTIFIER", "unrelated", 4, name="unrelated"))

    g.add_edge(Edge(source="p1", target="i1", label="REACHING_DEF"))
    g.add_edge(Edge(source="i1", target="c1", label="REACHING_DEF"))
    # AST edge from the noise node to the call — must NOT be walked.
    g.add_edge(Edge(source="n1", target="c1", label="AST"))
    return g


class TestTaintFlow:
    def test_flow_properties(self):
        flow = TaintFlow(elements=[
            TaintFlowElement(node_id="a", line_number=1, line_code="x"),
            TaintFlowElement(node_id="b", line_number=2, line_code="y"),
        ])
        assert flow.source.node_id == "a"
        assert flow.sink.node_id == "b"
        assert flow.line_numbers == [1, 2]
        assert flow.node_ids == ["a", "b"]

    def test_empty_flow_has_no_source_or_sink(self):
        flow = TaintFlow(elements=[])
        assert flow.source is None
        assert flow.sink is None
        assert flow.line_numbers == []


class TestCWETemplates:
    def test_supported_cwes_includes_buffer_overflow(self):
        assert "CWE-119" in supported_cwes()

    def test_get_template_returns_dataclass(self):
        t = get_template("CWE-119")
        assert isinstance(t, CWETemplate)
        assert "memcpy" in t.sinks

    def test_get_template_unknown_returns_none(self):
        assert get_template("CWE-9999") is None


class TestTaintExtractor:
    def test_requires_sinks(self):
        with pytest.raises(ValueError):
            TaintExtractor(sink_names=[])

    def test_unknown_cwe_raises(self):
        with pytest.raises(ValueError):
            TaintExtractor(cwe_id="CWE-9999")

    def test_finds_parameter_sources(self):
        g = _build_buffer_overflow_graph()
        ex = TaintExtractor(cwe_id="CWE-119")
        ids = {n.id for n in ex.find_sources(g)}
        assert "p1" in ids

    def test_finds_named_sinks(self):
        g = _build_buffer_overflow_graph()
        ex = TaintExtractor(cwe_id="CWE-119")
        ids = {n.id for n in ex.find_sinks(g)}
        assert "c1" in ids

    def test_extract_returns_param_to_sink_flow(self):
        g = _build_buffer_overflow_graph()
        ex = TaintExtractor(cwe_id="CWE-119")
        flows = ex.extract(g)
        assert len(flows) == 1
        assert flows[0].node_ids == ["p1", "i1", "c1"]
        assert flows[0].line_numbers == [1, 2, 3]

    def test_ignores_non_ddg_edges(self):
        g = _build_buffer_overflow_graph()
        ex = TaintExtractor(cwe_id="CWE-119")
        flows = ex.extract(g)
        # The AST-only path n1 -> c1 must not produce a flow.
        for f in flows:
            assert "n1" not in f.node_ids

    def test_explicit_names_override_template(self):
        g = _build_buffer_overflow_graph()
        ex = TaintExtractor(sink_names=["memcpy"], include_parameters_as_sources=True)
        flows = ex.extract(g)
        assert flows and flows[0].sink.node_id == "c1"


class TestTaintFlowTrimmer:
    def test_trim_returns_subgraph_of_flow_nodes(self):
        g = _build_buffer_overflow_graph()
        trimmer = TaintFlowTrimmer(cwe_id="CWE-119")
        result = trimmer.trim(g, target_node_id="c1")
        keep = set(result.nx_graph.nodes())
        # Flow nodes are kept; unrelated noise node is dropped.
        assert {"p1", "i1", "c1"}.issubset(keep)
        assert "n1" not in keep

    def test_trim_exposes_last_flows(self):
        g = _build_buffer_overflow_graph()
        trimmer = TaintFlowTrimmer(cwe_id="CWE-119")
        trimmer.trim(g, target_node_id="c1")
        assert len(trimmer.last_flows) == 1

    def test_no_fallback_when_no_flows(self):
        # Drop the DDG edges so no flows are found; trimmer must stay specific
        # to taint flows and not expand into a k-hop neighbourhood of target.
        g = _build_buffer_overflow_graph()
        nx_g = g.nx_graph
        ddg_edges = [
            (u, v, k) for u, v, k, d in nx_g.edges(keys=True, data=True)
            if d.get("label") == "REACHING_DEF"
        ]
        for u, v, k in ddg_edges:
            nx_g.remove_edge(u, v, key=k)

        trimmer = TaintFlowTrimmer(cwe_id="CWE-119")
        result = trimmer.trim(g, target_node_id="c1")
        assert trimmer.last_flows == []
        # Only the target anchor is kept; no neighbourhood padding.
        assert set(result.nx_graph.nodes()) == {"c1"}
