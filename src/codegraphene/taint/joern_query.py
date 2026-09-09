"""Real interprocedural dataflow queries via Joern's own CPGQL engine.

TaintExtractor and ProgramSlicer traverse the statically exported
REACHING_DEF/CDG edges from a plain `joern-export --repr all` DOT file --
these are intraprocedural only (Joern does not export a data-dependency
edge that crosses a function-call boundary). Finding a flow that crosses
call boundaries -- e.g. a tainted parameter passed into a helper function
that eventually reaches a sink -- requires Joern's own dataflow engine
(`io.joern.dataflowengineoss`, exposed as `.reachableByFlows()` in the
Joern shell), which does real interprocedural, path-sensitive traversal.

That engine only runs inside a Joern/JVM process, not in this Python
process, so this module shells out to `joern --script`. To avoid
re-parsing the source on every query, point it at a CPG binary persisted
via `JoernParser(keep_cpg_at=...)` (or any `cpg.bin` from a plain
`joern-parse` run) rather than a fresh source file -- `importCpg()` opens
an existing CPG directly. This does not eliminate the JVM startup cost
of each `joern --script` invocation (~2-5s); only Joern's own `--server`
mode (a long-lived JVM serving many queries) would do that, and isn't
implemented here.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

_SCRIPT_PATH = Path(__file__).parent / "scripts" / "reachable_by_flows.sc"


@dataclass
class FlowElement:
    """One step along a dataflow path."""

    code: str
    line_number: int | None = None


@dataclass
class JoernFlow:
    """One source-to-sink dataflow path found by Joern's dataflow engine."""

    elements: list[FlowElement] = field(default_factory=list)


def find_taint_flows(
    cpg_path: str,
    source_pattern: str,
    sink_pattern: str,
    joern_path: str = "joern",
    timeout_seconds: int = 180,
) -> list[JoernFlow]:
    """Find real interprocedural flows from parameters matching
    *source_pattern* to arguments of calls matching *sink_pattern*.

    Args:
        cpg_path: Path to an existing CPG binary. Not re-parsed -- Joern
                  opens it directly via `importCpg()`.
        source_pattern: Regex matched against parameter names.
        sink_pattern: Regex matched against call names.
        joern_path: Command or path to the `joern` executable.
        timeout_seconds: Subprocess timeout for the whole query.

    Returns:
        One :class:`JoernFlow` per path Joern's dataflow engine found,
        each listing the code (and line number, where available) at every
        step from source to sink.
    """
    if not os.path.exists(cpg_path):
        raise FileNotFoundError(f"CPG not found: {cpg_path}")

    cmd = [
        joern_path,
        "--script",
        str(_SCRIPT_PATH),
        "--param",
        f"cpgPath={os.path.abspath(cpg_path)}",
        "--param",
        f"sourcePattern={source_pattern}",
        "--param",
        f"sinkPattern={sink_pattern}",
    ]

    with tempfile.TemporaryDirectory() as workdir:
        # Joern's `importCpg` creates a `workspace/` project directory next
        # to the CPG's cwd -- run from a throwaway dir so that litter
        # doesn't land next to the caller's persisted cpg.bin.
        try:
            result = subprocess.run(
                cmd,
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Joern dataflow query timed out after {timeout_seconds}s"
            ) from exc

    if result.returncode != 0:
        details = (result.stderr or result.stdout or "").strip()
        if len(details) > 1000:
            details = details[-1000:]
        raise RuntimeError(f"Joern dataflow query failed (exit {result.returncode}): {details}")

    return _parse_flows(result.stdout)


def _parse_flows(stdout: str) -> list[JoernFlow]:
    flows: list[JoernFlow] = []
    current: JoernFlow | None = None
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if line == "FLOW_START":
            current = JoernFlow()
        elif line == "FLOW_END":
            if current is not None:
                flows.append(current)
            current = None
        elif line.startswith("ELEM|") and current is not None:
            # Code may itself contain "|" (e.g. C's `|` operator), so split
            # off the line number from the right -- it's the one field
            # guaranteed not to contain "|" -- rather than splitting from
            # the left.
            body = line[len("ELEM|"):]
            code, _, line_no = body.rpartition("|")
            current.elements.append(
                FlowElement(
                    code=code,
                    line_number=None if line_no in ("-1", "") else int(line_no),
                )
            )
    return flows
