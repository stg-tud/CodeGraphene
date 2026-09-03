"""Tests for NodeGranularity.RAW (the full, unfiltered CPG mode)."""

from codegraphene.core import NodeGranularity


def test_raw_accepts_any_node():
    # METHOD_PARAMETER_IN nodes have neither LINE_NUMBER+CODE (LINE) nor
    # NAME+FULL_NAME (METHOD) in the shape LINE/METHOD granularity expect --
    # RAW must still accept them, since it's meant to drop nothing.
    assert NodeGranularity.RAW.is_valid({"label": "METHOD_PARAMETER_OUT"})
    assert NodeGranularity.RAW.is_valid({})


def test_raw_label_uses_cpg_node_type():
    data = {"label": "CALL", "CODE": "foo(x)", "NAME": "foo"}
    assert NodeGranularity.RAW.extract_label(data) == "CALL"


def test_raw_still_extracts_line_number_when_present():
    assert NodeGranularity.RAW.extract_line_number({"LINE_NUMBER": "42"}) == 42
    assert NodeGranularity.RAW.extract_line_number({}) is None
