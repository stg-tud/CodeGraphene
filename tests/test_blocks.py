"""Tests for the C/C++ block analyzer."""

from codegraphene.blocks import (
    analyze_c_code,
    find_enclosing_blocks,
    smallest_enclosing_block,
)


FUNC_WITH_IF_ELSE = """\
int foo(int x) {
    if (x > 0) {
        return x;
    } else {
        return -x;
    }
}
"""


NESTED_FOR_WHILE = """\
int bar(int n) {
    int total = 0;
    for (int i = 0; i < n; i++) {
        while (total < 100) {
            total += i;
        }
    }
    return total;
}
"""


BRACELESS_IF = """\
int baz(int x) {
    if (x > 0)
        return x;
    return -x;
}
"""


DO_WHILE = """\
int qux(int n) {
    int i = 0;
    do {
        i++;
    } while (i < n);
    return i;
}
"""


class TestAnalyzeCCode:
    def test_detects_function(self):
        blocks = analyze_c_code(FUNC_WITH_IF_ELSE)
        funcs = [b for b in blocks if b.type == "function"]
        assert len(funcs) == 1
        assert funcs[0].name == "foo"
        assert funcs[0].start_line == 1
        assert funcs[0].end_line == 7

    def test_detects_if_and_else(self):
        types = [b.type for b in analyze_c_code(FUNC_WITH_IF_ELSE)]
        assert "if" in types
        assert "else" in types

    def test_detects_nested_for_and_while(self):
        blocks = analyze_c_code(NESTED_FOR_WHILE)
        types = [b.type for b in blocks]
        assert "for" in types
        assert "while" in types

        fors = [b for b in blocks if b.type == "for"]
        whiles = [b for b in blocks if b.type == "while"]
        # The while must be nested inside the for.
        assert fors[0].start_line < whiles[0].start_line
        assert whiles[0].end_line < fors[0].end_line

    def test_braceless_if_has_no_braces_flag(self):
        ifs = [b for b in analyze_c_code(BRACELESS_IF) if b.type == "if"]
        assert ifs and ifs[0].has_braces is False

    def test_do_while_recognized(self):
        types = [b.type for b in analyze_c_code(DO_WHILE)]
        assert "do-while" in types
        # The trailing `while(i < n);` should not be misidentified as a new while.
        assert "while" not in types


class TestEnclosingBlocks:
    def test_smallest_enclosing_returns_innermost(self):
        blocks = analyze_c_code(NESTED_FOR_WHILE)
        # `total += i;` lives at line 5 — innermost block is the while.
        inner = smallest_enclosing_block(5, blocks)
        assert inner is not None and inner.type == "while"

    def test_find_enclosing_returns_innermost_first(self):
        blocks = analyze_c_code(NESTED_FOR_WHILE)
        encl = find_enclosing_blocks(5, blocks)
        types = [b.type for b in encl]
        assert types[0] == "while"
        assert "for" in types
        assert "function" in types
