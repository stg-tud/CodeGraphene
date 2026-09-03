"""Tests for the sequential GraphPipeline execution model."""

from codegraphene.core import CodeGraph, Edge, Node
from codegraphene.pipeline import GraphPipeline
from codegraphene.parsers.base import BaseParser
from codegraphene.serializers.base import BaseSerializer
from codegraphene.serializers.text import CodeReconstructionSerializer
from codegraphene.trimmers.base import BaseTrimmer
from codegraphene.trimmers.khop import KHopTrimmer


class RecordingParser(BaseParser):
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def build_graph(self, file_path: str) -> CodeGraph:
        self.events.append(f"parser:{file_path}")
        graph = CodeGraph()
        graph.add_node(Node(id="1", label="TARGET", code="x = 1", line_number=1))
        graph.add_node(Node(id="2", label="OTHER", code="y = 2", line_number=2))
        graph.add_edge(Edge(source="1", target="2", label="CFG"))
        return graph


class ContextRecordingParser(BaseParser):
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def build_graph(self, file_path: str) -> CodeGraph:
        return CodeGraph()

    def run(self, current_graph=None, **context) -> CodeGraph:
        self.events.append(f"parser:{context.get('source_code')}:{context.get('language')}")
        graph = CodeGraph()
        graph.add_node(Node(id="1", label="TARGET", code="x = 1", line_number=1))
        graph.add_edge(Edge(source="1", target="1", label="SELF"))
        return graph


class RecordingTrimmer(BaseTrimmer):
    def __init__(self, name: str, events: list[str]) -> None:
        self.name = name
        self.events = events

    def trim(self, graph: CodeGraph, target_node_id: str) -> CodeGraph:
        self.events.append(f"{self.name}:{target_node_id}")
        return graph


class RecordingSerializer(BaseSerializer):
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def serialize(self, graph: CodeGraph) -> str:
        self.events.append(f"serializer:{graph.nx_graph.number_of_nodes()}")
        return "serialized"


def test_pipeline_runs_components_in_order():
    events: list[str] = []
    pipeline = GraphPipeline(
        components=[
            RecordingParser(events),
            RecordingTrimmer("trim-1", events),
            RecordingTrimmer("trim-2", events),
            RecordingSerializer(events),
        ]
    )

    output = pipeline.run(file_path="sample.py", target=1)

    # `GraphPipeline.run()` may return a PipelineResult wrapper; accept either.
    if hasattr(output, "output"):
        assert output.output == "serialized"
    else:
        assert output == "serialized"
    assert events == [
        "parser:sample.py",
        "trim-1:1",
        "trim-2:1",
        "serializer:2",
    ]


def test_pipeline_dry_run_reports_sequence():
    events: list[str] = []
    pipeline = GraphPipeline(
        components=[
            RecordingParser(events),
            RecordingTrimmer("trim-1", events),
            RecordingSerializer(events),
        ]
    )

    plan = pipeline.dry_run(file_path="sample.py", target=1)

    assert [step["name"] for step in plan] == [
        "RecordingParser",
        "trim-1",
        "RecordingSerializer",
    ]
    assert [step["output_type"] for step in plan] == [
        "CodeGraph",
        "CodeGraph",
        "str",
    ]
    assert events == []


def test_pipeline_dry_run_includes_serializer_settings():
    pipeline = GraphPipeline(
        components=[
            RecordingParser([]),
            RecordingTrimmer("trim-1", []),
            CodeReconstructionSerializer(
                line_template="{line} => {code}",
                separator=" | ",
            ),
        ]
    )

    plan = pipeline.dry_run(file_path="sample.py", target=1)

    serializer_step = plan[-1]
    assert serializer_step["name"] == "CodeReconstructionSerializer"
    assert serializer_step["line_template"] == "{line} => {code}"
    assert serializer_step["separator"] == " | "


def test_pipeline_forwards_source_code_context():
    events: list[str] = []
    pipeline = GraphPipeline(
        components=[
            ContextRecordingParser(events),
            RecordingSerializer(events),
        ]
    )

    output = pipeline.run(source_code="x = 1", language="python", target=1)

    if hasattr(output, "output"):
        assert output.output == "serialized"
    else:
        assert output == "serialized"
    assert events[0] == "parser:x = 1:python"


class TwoIslandParser(BaseParser):
    """Two disconnected components, each with one node matching label 'HIT'."""

    def build_graph(self, file_path: str) -> CodeGraph:
        graph = CodeGraph()
        graph.add_node(Node(id="hit-1", label="HIT", code="a", line_number=1))
        graph.add_node(Node(id="neighbor-1", label="OTHER", code="b", line_number=2))
        graph.add_edge(Edge(source="hit-1", target="neighbor-1", label="AST"))

        graph.add_node(Node(id="hit-2", label="HIT", code="c", line_number=10))
        graph.add_node(Node(id="neighbor-2", label="OTHER", code="d", line_number=11))
        graph.add_edge(Edge(source="hit-2", target="neighbor-2", label="AST"))
        return graph


def test_pipeline_multi_target_unions_khop_results_across_all_matches():
    pipeline = GraphPipeline(components=[TwoIslandParser(), KHopTrimmer(hops=1)])

    result = pipeline.run(file_path="two_islands.py", target="HIT")

    ids = {n.id for n in result.output.get_nodes()}
    assert ids == {"hit-1", "neighbor-1", "hit-2", "neighbor-2"}
    assert sorted(result.metadata["target_node_ids"]) == ["hit-1", "hit-2"]


def test_pipeline_single_target_match_is_unaffected_by_multi_target_path():
    """A target that matches exactly one node still takes the plain single-run path."""
    events: list[str] = []
    pipeline = GraphPipeline(
        components=[RecordingParser(events), RecordingTrimmer("trim", events)]
    )

    result = pipeline.run(file_path="sample.py", target="TARGET")

    assert events == ["parser:sample.py", "trim:1"]
    assert result.metadata["target_node_ids"] == ["1"]


def test_pipeline_accepts_a_list_of_trimmers_run_in_sequence():
    """Issue #5: trimmer=[...] runs each trimmer in order, same as components=."""
    events: list[str] = []
    pipeline = GraphPipeline(
        parser=RecordingParser(events),
        trimmer=[RecordingTrimmer("trim-1", events), RecordingTrimmer("trim-2", events)],
    )

    pipeline.run(file_path="sample.py", target=1)

    assert events == ["parser:sample.py", "trim-1:1", "trim-2:1"]