"""Tests for codegraphene.taint.joern_query (real interprocedural dataflow)."""

import os
import shutil

import pytest

from codegraphene.core import CodeGraph
from codegraphene.taint.joern_query import FlowElement, JoernFlow, _parse_flows, find_taint_flows


def test_parse_flows_handles_multiple_flows_and_pipe_in_code():
    stdout = "\n".join(
        [
            "NUM_FLOWS=2",
            "FLOW_START",
            "ELEM|char **argv|11",
            "ELEM|a | b|-1",  # code containing a literal '|' (e.g. C's bitwise-or)
            "FLOW_END",
            "FLOW_START",
            "ELEM|char *x|5",
            "FLOW_END",
        ]
    )
    flows = _parse_flows(stdout)
    assert flows == [
        JoernFlow(elements=[FlowElement("char **argv", 11), FlowElement("a | b", None)]),
        JoernFlow(elements=[FlowElement("char *x", 5)]),
    ]


def test_find_taint_flows_raises_for_missing_cpg(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_taint_flows(str(tmp_path / "does-not-exist.bin"), "src", "sink")


def test_code_graph_find_taint_flows_requires_cpg_path():
    graph = CodeGraph()
    with pytest.raises(ValueError, match="cpg_path is None"):
        graph.find_taint_flows("argv", "system")


@pytest.mark.integration
def test_real_interprocedural_flow_crosses_function_boundaries(tmp_path):
    """The whole point of this module: a flow that crosses two function-call
    boundaries (main -> process -> sink), which the statically exported
    REACHING_DEF/CDG edges cannot represent (confirmed separately: those
    edges never connect a call's argument to the callee's own parameter).
    """
    if shutil.which("joern") is None:
        pytest.skip("Joern CLI not found in PATH; skipping integration test")

    from codegraphene.parsers.joern import JoernParser

    code = """
    void sink(char *data) {
        system(data);
    }

    void process(char *input) {
        char buf[64];
        strcpy(buf, input);
        sink(buf);
    }

    int main(int argc, char **argv) {
        process(argv[1]);
        return 0;
    }
    """
    cpg_path = str(tmp_path / "cpg.bin")
    parser = JoernParser(keep_cpg_at=cpg_path)
    graph = parser.build_graph(source_code=code, language="c")

    assert graph.cpg_path == cpg_path
    assert os.path.exists(cpg_path)

    flows = graph.find_taint_flows(source_pattern="argv", sink_pattern="system")
    assert len(flows) >= 1
    all_code = " ".join(e.code for flow in flows for e in flow.elements)
    # The flow should span all three functions, not just the one containing argv.
    assert "argv" in all_code
    assert "buf" in all_code
    assert "data" in all_code

    # Reusing the same persisted CPG for a second, different query must not
    # require re-parsing (no build_graph()/JoernParser call in between).
    second = find_taint_flows(cpg_path, source_pattern="input", sink_pattern="system")
    assert len(second) >= 1
