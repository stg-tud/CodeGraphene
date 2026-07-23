import os
import shutil
import pytest

from codegraphene.parsers import manager
from codegraphene.core import CodeGraph, Node, NodeGranularity


class DummyParser:
    def __init__(self, prefix: str = "p"):
        self.prefix = prefix

    def run(self, file_path=None, source_code=None, language=None):
        cg = CodeGraph()
        # create a single node with id based on input
        key = file_path or (source_code[:10] if source_code else "input")
        node = Node(id=f"{self.prefix}:{key}", label=str(key), properties={})
        cg.add_node(node)
        return cg


def test_parse_many_sequential(tmp_path, monkeypatch):
    # Use local import path for DummyParser by injecting into a module
    import types

    mod = types.ModuleType("tests._dummy")
    mod.DummyParser = DummyParser
    import sys

    sys.modules["tests._dummy"] = mod

    inputs = [{"file_path": str(tmp_path / "a.py")}, {"source_code": "print(1)", "language": "python"}]
    results = manager.parse_many("tests._dummy.DummyParser", {"prefix": "x"}, inputs, parallel_workers=1)
    assert len(results) == 2
    for spec, res in results:
        assert isinstance(res, CodeGraph)


@pytest.mark.integration
def test_parse_many_parallel_joern(tmp_path):
    """
    Validates that parse_many can successfully distribute real Joern parsing 
    tasks across multiple background processes without GIL/state collision.
    """
    # Gate the test behind the environment flag and Joern availability
    if os.environ.get("RUN_REAL_JOERN") not in ("1", "true", "True") or shutil.which("joern") is None:
        pytest.skip("Skipping parallel Joern test (RUN_REAL_JOERN!=1 or joern not in PATH)")
    
    # Create two temporary Python files to parse concurrently
    file1 = tmp_path / "parallel_a.py"
    file1.write_text("x = 1\ny = x + 2")
    
    file2 = tmp_path / "parallel_b.py"
    file2.write_text("def foo():\n    return 'bar'")

    inputs = [
        {"file_path": str(file1)}, 
        {"file_path": str(file2)}
    ]
    
    # The manager will import JoernParser in the worker processes
    results = manager.parse_many(
        parser_path="codegraphene.parsers.joern.JoernParser",
        parser_kwargs={"granularity": NodeGranularity.LINE, "export_format": "dot"},
        inputs=inputs,
        parallel_workers=2
    )
    
    # Verify both files were parsed and returned valid CodeGraphs
    assert len(results) == 2
    for spec, res in results:
        assert isinstance(res, CodeGraph), f"Worker returned an exception instead of a graph: {res}"
        assert res.nx_graph.number_of_nodes() > 0
        assert res.nx_graph.number_of_edges() > 0