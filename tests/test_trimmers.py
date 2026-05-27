"""Tests for the trimmers sub-package."""

import pytest

from codegraphene.core import CodeGraph, Node, Edge
from codegraphene.trimmers.base import BaseTrimmer
from codegraphene.trimmers.khop import KHopTrimmer
from codegraphene.parsers.joern import JoernParser
from codegraphene.serializers.text import CodeReconstructionSerializer


def test_trimmer_and_serializer_with_joern(use_real_joern, tmp_path):
    """Optional end-to-end check: parse a real file with Joern, then trim and serialize.

    Enable by setting `RUN_REAL_JOERN=1` in the environment and ensuring `joern` is in PATH.
    """
    if not use_real_joern:
        pytest.skip("Skipping Joern-backed end-to-end test")

    # Use repository example if available, otherwise create a tiny Python file.
    repo_root = tmp_path.parent
    repo_sample = repo_root / "examples" / "sample_code.py"
    src = tmp_path / "sample_code.py"
    if repo_sample.exists():
        src.write_text(repo_sample.read_text())
    else:
        src.write_text("def f():\n    x = 1\n    return x\n")

    parser = JoernParser()
    graph = parser.build_graph(str(src))

    trimmer = KHopTrimmer(hops=1)
    trimmed = trimmer.trim(graph, target_node_id=next(iter(graph.get_nodes())).id)

    serializer = CodeReconstructionSerializer()
    out = serializer.serialize(trimmed)
    assert isinstance(out, str)
    assert len(out) > 0


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

    def test_run_requires_target_node_id(self):
        class ConcreteTrimmer(BaseTrimmer):
            def trim(self, graph: CodeGraph, target_node_id: str) -> CodeGraph:
                return graph

        trimmer = ConcreteTrimmer()
        graph = _make_simple_graph()

        with pytest.raises(ValueError):
            trimmer.run(current_graph=graph)


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
        """KHopTrimmer returns a trimmed graph object."""
        trimmer = KHopTrimmer(hops=1)
        graph = _make_simple_graph()
        result = trimmer.trim(graph, target_node_id="2")
        assert isinstance(result, CodeGraph)
        assert result.nx_graph.number_of_nodes() == graph.nx_graph.number_of_nodes()

    def test_run_uses_trim(self):
        trimmer = KHopTrimmer(hops=1)
        graph = _make_simple_graph()
        result = trimmer.run(current_graph=graph, target_node_id="2")
        assert isinstance(result, CodeGraph)
