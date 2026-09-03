"""Tests for the serializers sub-package."""

import pytest

from codegraphene.core import CodeGraph, Edge, Node
from codegraphene.serializers.base import BaseSerializer
from codegraphene.serializers.text import CodeReconstructionSerializer, TextualGraphSerializer


class ConcreteSerializer(BaseSerializer):
    def serialize(self, graph: CodeGraph) -> str:
        return "ok"


def _make_simple_graph() -> CodeGraph:
    graph = CodeGraph()
    graph.add_node(Node(id="1", label="ASSIGN", code="a = 1", line_number=1))
    graph.add_node(Node(id="2", label="RETURN", code="return a", line_number=2))
    graph.add_edge(Edge(source="1", target="2", label="CFG"))
    return graph


class TestBaseSerializer:
    def test_abstract_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            BaseSerializer()  # type: ignore[abstract]

    def test_run_uses_serialize(self):
        serializer = ConcreteSerializer()
        graph = _make_simple_graph()

        assert serializer.run(current_graph=graph) == "ok"


class TestCodeReconstructionSerializer:
    def test_defaults_keep_current_format(self):
        serializer = CodeReconstructionSerializer()
        graph = _make_simple_graph()

        result = serializer.serialize(graph)

        assert result == "Line 1: a = 1\nLine 2: return a"

    def test_custom_output_preferences_are_supported(self):
        serializer = CodeReconstructionSerializer(
            line_template="{line} => {code}",
            separator=" | ",
        )
        graph = _make_simple_graph()

        result = serializer.serialize(graph)

        assert result == "1 => a = 1 | 2 => return a"
        assert serializer.describe()["line_template"] == "{line} => {code}"
        assert serializer.describe()["separator"] == " | "


class TestTextualGraphSerializer:
    def test_serializes_edges(self):
        serializer = TextualGraphSerializer()
        graph = _make_simple_graph()

        assert serializer.serialize(graph) == "Node 1 CFG Node 2"