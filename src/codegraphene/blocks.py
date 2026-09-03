"""
Regex-based C/C++ block detection for slice context expansion.

Ported from dev-taktile/master-thesis/src/taint/c_blocks.py (itself adapted
from LLMxCPG's c_parser.py). Works on the kind of single-function snippets
common in PrimeVul; brittle on macros and multi-line declarations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class CodeBlock:
    """A syntactic block; line numbers are 1-indexed and inclusive."""

    type: str  # 'function' | 'if' | 'else if' | 'else' | 'for' | 'while' | 'do-while'
    start_line: int
    end_line: int
    name: Optional[str] = None
    has_braces: bool = True


# Function definitions: a return-type prefix then `name(...)\s*{` on one line.
# Requiring the type prefix is what excludes `if (...) { ... }` style headers.
_FUNC_RE = re.compile(r"^\s*[\w\s\*&]+?(?:\*\s*|\s+)(\w+)\s*\([^)]*\)\s*\{")

_CONTROL_KEYWORDS = frozenset({
    "if", "else", "for", "while", "do", "switch", "case", "default",
    "return", "sizeof", "break", "continue", "goto",
})


def _indentation(line: str) -> int:
    return len(line) - len(line.lstrip())


def _is_meaningful(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if s.startswith("//") or s.startswith("/*") or s.startswith("*"):
        return False
    return True


class _CCodeAnalyzer:
    def __init__(self, source_code: str) -> None:
        self.lines = source_code.splitlines()
        self.blocks: List[CodeBlock] = []

    def analyze(self) -> List[CodeBlock]:
        self._scan_functions()
        self._scan_control_structures()
        return sorted(self.blocks, key=lambda b: (b.start_line, b.end_line))

    # --- brace matching --------------------------------------------------

    def _matching_brace(self, open_line_idx: int) -> int:
        """Index of the `}` that closes the `{` opened on open_line_idx; -1 if unbalanced."""
        first = self.lines[open_line_idx]
        depth = 1 + first.count("{") - 1 - first.count("}")
        if depth == 0:
            return open_line_idx
        for i in range(open_line_idx + 1, len(self.lines)):
            line = self.lines[i]
            depth += line.count("{") - line.count("}")
            if depth == 0:
                return i
        return -1

    # --- braceless single-statement bodies -------------------------------

    def _next_statement_end(self, header_line_idx: int) -> int:
        body_start = -1
        for i in range(header_line_idx + 1, len(self.lines)):
            if _is_meaningful(self.lines[i]):
                body_start = i
                break
        if body_start == -1:
            return header_line_idx

        body_indent = _indentation(self.lines[body_start])
        last = body_start
        for i in range(body_start + 1, len(self.lines)):
            line = self.lines[i]
            if not _is_meaningful(line):
                continue
            if _indentation(line) > body_indent:
                last = i
            else:
                break
        return last

    # --- scanners --------------------------------------------------------

    def _scan_functions(self) -> None:
        for i, line in enumerate(self.lines):
            m = _FUNC_RE.match(line)
            if not m:
                continue
            name = m.group(1)
            if name in _CONTROL_KEYWORDS:
                continue
            end = self._matching_brace(i)
            if end == -1:
                continue
            self.blocks.append(CodeBlock(
                type="function",
                start_line=i + 1,
                end_line=end + 1,
                name=name,
            ))

    def _scan_control_structures(self) -> None:
        # Order matters: longer-keyword variants first.
        keyword_tests = [
            ("else if ", "else if"),
            ("} else if ", "else if"),
            ("else if(", "else if"),
            ("if ", "if"),
            ("if(", "if"),
            ("} else", "else"),
            ("else", "else"),
            ("for ", "for"),
            ("for(", "for"),
            ("while ", "while"),
            ("while(", "while"),
            ("do", "do-while"),
        ]

        for i, raw in enumerate(self.lines):
            stripped = raw.strip()
            if not stripped:
                continue

            block_type: Optional[str] = None
            for prefix, btype in keyword_tests:
                if stripped.startswith(prefix):
                    # `do` must be an exact token, not `double` / `done`.
                    if btype == "do-while" and not (
                        stripped == "do" or stripped.startswith("do {") or stripped.startswith("do{")
                    ):
                        continue
                    block_type = btype
                    break
            if block_type is None:
                continue

            # The `while(...)` tail of a do-while is not a new while-block.
            if block_type == "while" and any(
                b.type == "do-while" and b.end_line == i + 1 for b in self.blocks
            ):
                continue

            has_braces = "{" in stripped
            if has_braces:
                end = self._matching_brace(i)
                if end == -1:
                    continue
                self.blocks.append(CodeBlock(block_type, i + 1, end + 1))
            else:
                end = self._next_statement_end(i)
                self.blocks.append(CodeBlock(block_type, i + 1, end + 1, has_braces=False))


def analyze_c_code(source_code: str) -> List[CodeBlock]:
    """Return sorted block ranges for a C/C++ source string."""
    return _CCodeAnalyzer(source_code).analyze()


def find_enclosing_blocks(line: int, blocks: List[CodeBlock]) -> List[CodeBlock]:
    """All blocks containing `line`, innermost first."""
    enclosing = [b for b in blocks if b.start_line <= line <= b.end_line]
    enclosing.sort(key=lambda b: b.start_line, reverse=True)
    return enclosing


def smallest_enclosing_block(line: int, blocks: List[CodeBlock]) -> Optional[CodeBlock]:
    enclosing = find_enclosing_blocks(line, blocks)
    return enclosing[0] if enclosing else None
