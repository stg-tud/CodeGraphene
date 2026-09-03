from codegraphene.pipeline import GraphPipeline
from codegraphene.core import PipelineResult, NodeGranularity
from codegraphene.trimmers.khop import KHopTrimmer
from codegraphene.serializers.text import CodeReconstructionSerializer


class FakeRawParser:
    """Simulates a parser returning a raw string (e.g. export_format=json)."""

    def run(self, current_graph=None, **context):
        return '{"raw": "json output"}'

    def describe(self):
        return {
            "name": "FakeRawParser",
            "component_type": "FakeRawParser",
            "input_type": "file_path",
            "output_type": "str",
            "requires_context": [],
            "capabilities": [],
        }


def test_pipeline_always_returns_pipeline_result():
    pipeline = GraphPipeline(
        components=[
            FakeRawParser(),
            KHopTrimmer(hops=1),
            CodeReconstructionSerializer(granularity=NodeGranularity.LINE),
        ]
    )
    result = pipeline.run(file_path="examples/sample_code.py", target=1)
    assert isinstance(result, PipelineResult)


def test_pipeline_short_circuit_metadata():
    pipeline = GraphPipeline(components=[FakeRawParser()])
    result = pipeline.run(file_path="examples/sample_code.py", target=1)
    assert result.metadata["short_circuited"] is True
    assert result.output_type == "str"
    assert result.kind == "joern_export"