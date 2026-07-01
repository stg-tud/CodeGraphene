"""Tests for the cleaners sub-package."""

import pytest
from unittest.mock import patch
from codegraphene.cleaners.base import BaseCleaner
from codegraphene.cleaners.black_formatter import BlackFormatter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class ConcreteClean(BaseCleaner):
    """Minimal concrete cleaner for testing the abstract interface."""
    def clean(self, source_code: str) -> str:
        return source_code.upper()


MESSY_PYTHON = "x=1\ny =  2\ndef   foo( ):\n    pass\n"
CLEAN_PYTHON = 'x = 1\ny = 2\n\n\ndef foo():\n    pass\n'


# ---------------------------------------------------------------------------
# BaseCleaner
# ---------------------------------------------------------------------------

class TestBaseCleaner:

    def test_abstract_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            BaseCleaner()  # type: ignore[abstract]

    def test_run_reads_source_code_from_context(self):
        cleaner = ConcreteClean()
        result = cleaner.run(source_code="hello")
        assert result == "HELLO"

    def test_run_reads_source_code_from_current_graph(self):
        """A string passed as current_graph should be treated as source text."""
        cleaner = ConcreteClean()
        result = cleaner.run(current_graph="hello")
        assert result == "HELLO"

    def test_run_reads_source_code_from_file(self, tmp_path):
        src = tmp_path / "sample.py"
        src.write_text("hello")
        cleaner = ConcreteClean()
        result = cleaner.run(file_path=str(src))
        assert result == "HELLO"

    def test_run_prefers_source_code_over_current_graph(self):
        cleaner = ConcreteClean()
        result = cleaner.run(current_graph="from_graph", source_code="from_context")
        assert result == "FROM_CONTEXT"

    def test_run_raises_if_no_source_available(self):
        cleaner = ConcreteClean()
        with pytest.raises(ValueError, match="requires"):
            cleaner.run()

    def test_describe_reports_text_to_text_contract(self):
        cleaner = ConcreteClean()
        info = cleaner.describe()
        assert info["input_type"] == "str"
        assert info["output_type"] == "str"


# ---------------------------------------------------------------------------
# BlackFormatter
# ---------------------------------------------------------------------------

class TestBlackFormatter:

    def test_instantiation(self):
        fmt = BlackFormatter()
        assert fmt.language == "python"

    def test_formats_messy_python(self):
        fmt = BlackFormatter()
        result = fmt.clean(MESSY_PYTHON)
        assert result == CLEAN_PYTHON

    def test_unsupported_language_returns_source_unchanged(self):
        fmt = BlackFormatter(language="java")
        result = fmt.clean("class Foo {}")
        assert result == "class Foo {}"

    def test_already_clean_input_is_unchanged(self):
        """Black is idempotent: formatting already-clean code is a no-op."""
        fmt = BlackFormatter()
        result = fmt.clean(CLEAN_PYTHON)
        assert result == CLEAN_PYTHON

    def test_black_not_installed_returns_source_unchanged(self):
        fmt = BlackFormatter()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = fmt.clean("x=1")
        assert result == "x=1"

    def test_black_syntax_error_raises_runtime_error(self):
        fmt = BlackFormatter()
        with pytest.raises(RuntimeError, match="black failed"):
            fmt.clean("def foo(:\n    pass\n")

    def test_describe_reports_formatter_metadata(self):
        fmt = BlackFormatter()
        info = fmt.describe()
        assert info["formatter"] == "black"
        assert info["language"] == "python"
        assert info["input_type"] == "str"
        assert info["output_type"] == "str"
