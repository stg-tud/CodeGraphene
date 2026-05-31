"""Tests for the parsers sub-package."""

import pytest

from codegraphene.core import CodeGraph
from codegraphene.parsers.base import BaseParser
from codegraphene.parsers.joern import JoernParser


class ConcreteParser(BaseParser):
    """Minimal concrete parser for testing the abstract interface."""

    # Add simple test for building a graph from a file path (returns empty graph for now)
    def build_graph(self, file_path: str) -> CodeGraph:
        graph = CodeGraph()
        # In a real implementation, we would parse the file and populate the graph
        return graph


class TestBaseParser:
    def test_abstract_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            BaseParser()  # type: ignore[abstract]

    def test_concrete_subclass_returns_code_graph(self):
        parser = ConcreteParser()
        graph = parser.build_graph("dummy.dot")
        assert isinstance(graph, CodeGraph)


class TestJoernParserUnit:
    """Unit tests for JoernParser that don't require real DOT files."""

    def test_instantiation(self):
        parser = JoernParser()
        assert isinstance(parser, BaseParser)

    def test_build_graph_missing_file_raises(self, tmp_path):
        parser = JoernParser()
        with pytest.raises(Exception):
            parser.build_graph(str(tmp_path / "nonexistent.dot"))

# Joern parser installation has to be added for this test to work, so we can skip it for now
#     def test_build_graph_with_dot_file(self, tmp_path):
#         dot_content = """digraph {
#     "1" [LINE_NUMBER="10" CODE="x = 1" label="ASSIGN"];
#     "2" [LINE_NUMBER="11" CODE="y = 2" label="ASSIGN"];
#     "1" -> "2" [label="CFG"];
# }"""
#         dot_file = tmp_path / "test.dot"
#         dot_file.write_text(dot_content)

#         parser = JoernParser()
#         graph = parser.build_graph(str(dot_file))

#         assert isinstance(graph, CodeGraph)
#         assert graph.nx_graph.number_of_nodes() == 2
#         assert graph.nx_graph.number_of_edges() == 1

# #     def test_build_graph_skips_nodes_without_code(self, tmp_path):
# #         dot_content = """digraph {
# #     "1" [LINE_NUMBER="10" CODE="x = 1" label="ASSIGN"];
# #     "2" [label="NO_CODE_HERE"];
# # }"""
# #         dot_file = tmp_path / "test.dot"
# #         dot_file.write_text(dot_content)

# #         parser = JoernParser()
# #         graph = parser.build_graph(str(dot_file))

# #         assert graph.nx_graph.number_of_nodes() == 1

#     def test_build_graph_invalid_line_number(self, tmp_path):
#         dot_content = """digraph {
#     "1" [LINE_NUMBER="abc" CODE="x = 1" label="ASSIGN"];
# }"""
#         dot_file = tmp_path / "test.dot"
#         dot_file.write_text(dot_content)

#         parser = JoernParser()
#         graph = parser.build_graph(str(dot_file))

#         nodes = graph.get_nodes()
#         assert nodes[0].line_number == -1
