import os
import shutil
import pytest

from codegraphene.core import NodeGranularity
from codegraphene.parsers.joern import JoernParser
from codegraphene.trimmers.khop import KHopTrimmer
from codegraphene.serializers.text import CodeReconstructionSerializer
from codegraphene.pipeline import GraphPipeline


@pytest.mark.integration
def test_joern_parse_and_pipeline_end_to_end():
    # Skip if Joern CLI not available in PATH
    if shutil.which("joern") is None:
        pytest.skip("Joern CLI not found in PATH; skipping integration test")

    # locate sample file from repository
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sample = os.path.normpath(os.path.join(repo_root, "examples", "sample_code.py"))
    assert os.path.exists(sample), f"Sample file not found at {sample}"

    parser = JoernParser(granularity=NodeGranularity.LINE)
    trimmer = KHopTrimmer(hops=1)
    serializer = CodeReconstructionSerializer(granularity=NodeGranularity.LINE)
    pipeline = GraphPipeline(parser=parser, trimmer=trimmer, serializer=serializer)

    # Parser invariant: must produce a non-empty graph with line-aware nodes.
    parsed_graph = parser.build_graph(sample)
    assert parsed_graph.nx_graph.number_of_nodes() > 0
    assert parsed_graph.nx_graph.number_of_edges() >= 0

    candidates = [
        node for node in parsed_graph.get_nodes()
        if isinstance(node.line_number, int) and node.line_number > 0
    ]
    assert candidates, "Expected at least one line-level node from Joern output"
    target_line = candidates[0].line_number

    # Trimmer invariant: resolved target should exist and trimming should not expand graph.
    target_nodes = parser.granularity.find_target_nodes(parsed_graph, target_line)
    assert target_nodes, "Target line was not resolvable to any graph node"
    trimmed_graph = trimmer.trim(parsed_graph, target_nodes[0].id)
    assert trimmed_graph.nx_graph.number_of_nodes() > 0
    assert trimmed_graph.nx_graph.number_of_nodes() <= parsed_graph.nx_graph.number_of_nodes()

    # Serializer invariant: output must contain meaningful non-whitespace text.
    serialized = serializer.serialize(trimmed_graph)
    assert isinstance(serialized, str)
    assert serialized.strip()

    # Full pipeline invariant: full run returns non-empty string for resolved target.
    result = pipeline.run(file_path=sample, target=target_line)

    # `GraphPipeline.run()` may return a PipelineResult wrapper; accept either.
    if hasattr(result, "output"):
        assert isinstance(result.output, str)
        assert result.output.strip()
    else:
        assert isinstance(result, str)
        assert result.strip()
