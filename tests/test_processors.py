"""Tests for the Processor category (issue #14, second half)."""

from codegraphene.processors.base import BaseProcessor
from codegraphene.processors.method_splitter import MethodSplitterProcessor


SAMPLE = '''\
def foo(x):
    return x + 1


class C:
    def bar(self):
        return 2
'''


def test_method_splitter_extracts_each_function_and_method():
    proc = MethodSplitterProcessor()
    snippets = proc.process(SAMPLE)
    assert len(snippets) == 2
    assert "def foo(x):" in snippets[0]
    assert "return x + 1" in snippets[0]
    assert "def bar(self):" in snippets[1]


def test_method_splitter_runs_through_component_interface():
    proc = MethodSplitterProcessor()
    result = proc.run(source_code=SAMPLE)
    assert len(result) == 2


def test_method_splitter_describe_reports_text_to_texts():
    proc = MethodSplitterProcessor()
    info = proc.describe()
    assert info["input_type"] == "Text/Code/Python"
    assert info["output_type"] == "Texts/Code/Python"


def test_base_processor_requires_an_input_item():
    class NoOpProcessor(BaseProcessor):
        def process(self, item):
            return item

    proc = NoOpProcessor()
    try:
        proc.run()
        assert False, "expected ValueError when no input item is available"
    except ValueError:
        pass
