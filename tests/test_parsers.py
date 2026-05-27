"""Tests for the parsers sub-package."""

import subprocess

import pytest

from codegraphene.core import CodeGraph, Node, Edge
from codegraphene.parsers.base import BaseParser
from codegraphene.parsers.joern import JoernParser


class ConcreteParser(BaseParser):
    """Minimal concrete parser for testing the abstract interface."""

    def build_graph(self, file_path: str) -> CodeGraph:
        return CodeGraph()


class TestBaseParser:
    def test_abstract_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            BaseParser()  # type: ignore[abstract]

    def test_concrete_subclass_returns_code_graph(self):
        parser = ConcreteParser()
        graph = parser.build_graph("dummy.dot")
        assert isinstance(graph, CodeGraph)

    def test_run_uses_build_graph(self):
        parser = ConcreteParser()
        graph = parser.run(file_path="dummy.dot")
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

    def test_build_graph_with_dot_file(self, tmp_path, monkeypatch, use_real_joern):
        dot_content = """digraph {
    "1" [LINE_NUMBER="10" CODE="x = 1" label="ASSIGN"];
    "2" [LINE_NUMBER="11" CODE="y = 2" label="ASSIGN"];
    "1" -> "2" [label="CFG"];
}"""
        dot_file = tmp_path / "test.dot"
        dot_file.write_text(dot_content)

        parser = JoernParser()
        if not use_real_joern:
            # Avoid invoking external joern binaries in unit tests.
            monkeypatch.setattr(parser, "_generate_dot_file", lambda file_path, temp_dir: str(dot_file))
            graph = parser.build_graph(str(dot_file))
        else:
            # Use a small real source file to let Joern generate the DOT
            src = tmp_path / "sample_code.py"
            # copy a minimal sample from repository examples
            repo_sample = (tmp_path.parent / "examples" / "sample_code.py")
            if not repo_sample.exists():
                # fallback: create a tiny file
                src.write_text("def f():\n    x = 1\n    return x\n")
            else:
                src.write_text(repo_sample.read_text())
            graph = parser.build_graph(str(src))

        assert isinstance(graph, CodeGraph)
        if not use_real_joern:
            assert graph.nx_graph.number_of_nodes() == 2
            assert graph.nx_graph.number_of_edges() == 1
        else:
            # With a real Joern run we can't rely on the tiny DOT fixture expectations;
            # just assert that Joern produced a non-empty graph.
            assert graph.nx_graph.number_of_nodes() > 0
            assert graph.nx_graph.number_of_edges() >= 0

    def test_run_accepts_source_code_and_language(self, tmp_path, monkeypatch):
        dot_content = """digraph {
    "1" [LINE_NUMBER="10" CODE="x = 1" label="ASSIGN"];
}"""
        dot_file = tmp_path / "test.dot"
        dot_file.write_text(dot_content)

        parser = JoernParser()
        seen_input = {}

        def fake_generate_export_artifact(file_path, temp_dir):
            seen_input["file_path"] = file_path
            return str(dot_file)

        monkeypatch.setattr(parser, "_generate_export_artifact", fake_generate_export_artifact)

        graph = parser.run(source_code="x = 1\n", language="python")

        assert isinstance(graph, CodeGraph)
        assert seen_input["file_path"].endswith(".py")

    def test_raw_export_mode_returns_text_artifact(self, tmp_path, monkeypatch):
        source_file = tmp_path / "sample.py"
        source_file.write_text("x = 1\n")

        parser = JoernParser(export_format="json")
        monkeypatch.setattr(parser, "_run_joern_parse", lambda file_path, cpg_out: None)
        monkeypatch.setattr(parser, "_run_joern_export", lambda cpg_out, export_out: None)
        monkeypatch.setattr(parser, "_load_raw_export_artifact", lambda export_out: '{"nodes": []}')

        result = parser.build_graph(str(source_file))

        assert isinstance(result, str)
        assert result == '{"nodes": []}'
        assert parser.describe()["output_type"] == "str"

    def test_build_graph_skips_nodes_without_code(self, tmp_path, monkeypatch, use_real_joern):
        dot_content = """digraph {
    "1" [LINE_NUMBER="10" CODE="x = 1" label="ASSIGN"];
    "2" [label="NO_CODE_HERE"];
}"""
        dot_file = tmp_path / "test.dot"
        dot_file.write_text(dot_content)

        parser = JoernParser()
        if not use_real_joern:
            # Avoid invoking external joern binaries in unit tests.
            monkeypatch.setattr(parser, "_generate_dot_file", lambda file_path, temp_dir: str(dot_file))
            graph = parser.build_graph(str(dot_file))
        else:
            repo_sample = (tmp_path.parent / "examples" / "sample_code.py")
            src = tmp_path / "sample_code.py"
            if not repo_sample.exists():
                src.write_text("def f():\n    x = 1\n    return x\n")
            else:
                src.write_text(repo_sample.read_text())
            graph = parser.build_graph(str(src))

        if not use_real_joern:
            assert graph.nx_graph.number_of_nodes() == 1
        else:
            # Real Joern run yields a full graph; ensure it's non-empty.
            assert graph.nx_graph.number_of_nodes() > 0

    def test_build_graph_invalid_line_number(self, tmp_path, monkeypatch, use_real_joern):
        dot_content = """digraph {
    "1" [LINE_NUMBER="abc" CODE="x = 1" label="ASSIGN"];
}"""
        dot_file = tmp_path / "test.dot"
        dot_file.write_text(dot_content)

        parser = JoernParser()
        if not use_real_joern:
            # Avoid invoking external joern binaries in unit tests.
            monkeypatch.setattr(parser, "_generate_dot_file", lambda file_path, temp_dir: str(dot_file))
            graph = parser.build_graph(str(dot_file))
        else:
            repo_sample = (tmp_path.parent / "examples" / "sample_code.py")
            src = tmp_path / "sample_code.py"
            if not repo_sample.exists():
                src.write_text("def f():\n    x = 1\n    return x\n")
            else:
                src.write_text(repo_sample.read_text())
            graph = parser.build_graph(str(src))

        nodes = graph.get_nodes()
        if not use_real_joern:
            assert nodes[0].line_number == -1
        else:
            # For a real Joern parse, line numbers should be integers (>= 1)
            assert isinstance(nodes[0].line_number, int)
            assert nodes[0].line_number >= 1

    def test_run_joern_parse_passes_timeout(self, monkeypatch):
        parser = JoernParser(parse_timeout_seconds=7)
        captured = {}

        def fake_run(cmd, check, timeout, capture_output, text):
            captured["timeout"] = timeout
            class Result:
                returncode = 0
                stdout = ""
                stderr = ""
            return Result()

        monkeypatch.setattr("codegraphene.parsers.joern.subprocess.run", fake_run)
        parser._run_joern_parse("input.py", "out.bin")
        assert captured["timeout"] == 7

    def test_run_joern_parse_timeout_raises_runtime_error(self, monkeypatch):
        parser = JoernParser(parse_timeout_seconds=1)

        def fake_run(cmd, check, timeout, capture_output, text):
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)

        monkeypatch.setattr("codegraphene.parsers.joern.subprocess.run", fake_run)
        with pytest.raises(RuntimeError, match="timed out"):
            parser._run_joern_parse("input.py", "out.bin")

    def test_run_joern_parse_called_process_error_raises_runtime_error(self, monkeypatch):
        parser = JoernParser()

        def fake_run(cmd, check, timeout, capture_output, text):
            raise subprocess.CalledProcessError(
                returncode=2,
                cmd=cmd,
                output="",
                stderr="parse failure",
            )

        monkeypatch.setattr("codegraphene.parsers.joern.subprocess.run", fake_run)
        with pytest.raises(RuntimeError, match="failed with exit code 2"):
            parser._run_joern_parse("input.py", "out.bin")
