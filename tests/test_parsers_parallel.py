import pytest

from codegraphene.parsers import manager
from codegraphene.core import CodeGraph, Node


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
