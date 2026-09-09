from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Dict, Iterator, List, Set, Union

import networkx as nx

TargetSpec = Union[str, int, "re.Pattern[str]", Callable[["Node"], bool]]


class BaseComponent(ABC):
    """Shared base class for pipeline modules.

    Components expose a tiny, uniform contract so the pipeline can inspect
    and execute them in sequence.
    """

    name: str | None = None

    @abstractmethod
    def run(self, current_graph=None, **context):
        """Execute the component with the given graph and context.

        Issue #10 asks for a common module API so the pipeline can call every
        parser, trimmer, and serializer through the same entry point.
        """

    def describe(self) -> dict[str, Any]:
        """Return metadata used by dry-run planning and logging."""
        return {
            "name": self.name or self.__class__.__name__,
            "component_type": self.__class__.__name__,
            "input_type": "CodeGraph",
            "output_type": "CodeGraph",
            "requires_context": [],
            "capabilities": [],
        }

    def modules(self) -> Iterator[BaseComponent]:
        """Yield nested modules if the component acts as a container."""
        return iter(())


class NodeGranularity:
    """Defines which CPG node attributes are required, and which to use as the label."""
    LINE:   ClassVar[NodeGranularity]
    METHOD: ClassVar[NodeGranularity]
    FILE:   ClassVar[NodeGranularity]
    RAW:    ClassVar[NodeGranularity]

    def __init__(
        self,
        required_attrs: Set[str],
        label_attr: str,
        code_attr: str,
        granularity_name: str,
        line_attr: str | None = None,
    ) -> None:
        self.required_attrs = frozenset(required_attrs)
        self.label_attr = label_attr
        self.code_attr = code_attr
        self.line_attr = line_attr
        self.granularity_name = granularity_name

    def is_valid(self, data: dict) -> bool:
        return self.required_attrs.issubset(data.keys())

    def extract_label(self, data: dict) -> str:
        return data.get(self.label_attr, "UNKNOWN")

    def extract_code(self, properties: dict) -> str | None:
        return properties.get(self.code_attr)

    def extract_line_number(self, properties: dict) -> int | None:
        if self.line_attr is None:
            return None
        try:
            return int(properties[self.line_attr])
        except (KeyError, ValueError):
            return None

    def find_target_nodes(self, graph: CodeGraph, target: TargetSpec) -> list[Node]:
        """Return nodes matching *target*.

        Accepts an ``int`` (line number, only meaningful when this
        granularity has a ``line_attr``), a ``str`` (exact label match), a
        compiled ``re.Pattern`` (searched against the node's label and code,
        e.g. to find any CALL node invoking a function matching a pattern),
        or a ``Callable[[Node], bool]`` predicate for arbitrary matching.
        """
        if isinstance(target, re.Pattern):
            return [
                node for node in graph.get_nodes()
                if target.search(node.label or "") or (node.code and target.search(node.code))
            ]
        if callable(target):
            return [node for node in graph.get_nodes() if target(node)]

        matches = []
        for node in graph.get_nodes():
            if self.line_attr is not None and isinstance(target, int):
                if self.extract_line_number(node.properties) == target:
                    matches.append(node)
            else:
                if node.label == str(target):
                    matches.append(node)
        return matches


NodeGranularity.LINE = NodeGranularity(
    required_attrs={"LINE_NUMBER", "CODE"},
    label_attr="label",
    code_attr="CODE",
    line_attr="LINE_NUMBER",
    granularity_name="LINE",
)
NodeGranularity.METHOD = NodeGranularity(
    required_attrs={"NAME", "FULL_NAME"},
    label_attr="NAME",
    code_attr="FULL_NAME",
    line_attr=None,
    granularity_name="METHOD",
)
NodeGranularity.FILE = NodeGranularity(
    required_attrs={"NAME"},
    label_attr="NAME",
    code_attr="NAME",
    line_attr=None,
    granularity_name="FILE",
)
NodeGranularity.RAW = NodeGranularity(
    # Empty required_attrs: every CPG node type passes is_valid(), so no
    # node or edge is dropped. This is the full, unfiltered CPG -- needed
    # by trimmers that traverse semantic edges (REACHING_DEF, CDG), since
    # those edges reach node types (METHOD, METHOD_PARAMETER_IN/OUT,
    # METHOD_RETURN, ...) that LINE/METHOD/FILE granularity filter out.
    # label_attr="label" uses the DOT label (the actual CPG node type,
    # e.g. "CALL", "METHOD") rather than a semantic name, since that's the
    # one attribute every node type has -- also the natural vocabulary key
    # for GNN-style node/edge type embeddings.
    required_attrs=set(),
    label_attr="label",
    code_attr="CODE",
    line_attr="LINE_NUMBER",
    granularity_name="RAW",
)


@dataclass
class Node:
    id: str
    label: str
    properties: Dict[str, Any] = field(default_factory=dict)
    code: str | None = None
    line_number: int | None = None

    def __post_init__(self) -> None:
        if self.code is None and "CODE" in self.properties:
            self.code = self.properties["CODE"]
        if self.line_number is None and "LINE_NUMBER" in self.properties:
            try:
                self.line_number = int(self.properties["LINE_NUMBER"])
            except (TypeError, ValueError):
                self.line_number = None
        if self.code is not None:
            self.properties.setdefault("CODE", self.code)
        if self.line_number is not None:
            self.properties.setdefault("LINE_NUMBER", self.line_number)
        if self.label is not None:
            self.properties.setdefault("label", self.label)

    def __getitem__(self, key: str) -> Any:
        if key == "id":
            return self.id
        if key == "label":
            return self.label
        if key == "properties":
            return self.properties
        if key == "code":
            return self.code
        if key == "line_number":
            return self.line_number
        raise KeyError(key)


@dataclass
class Edge:
    source: str
    target: str
    label: str


@dataclass
class PipelineResult:
    """Wrapper for all pipeline.run() outputs.

    Ensures callers always receive the same type regardless of
    whether the pipeline completed fully or short-circuited.
    """

    output: Any
    kind: str
    """One of: 'codegraph', 'serialized_code', 'joern_export'."""
    output_type: str
    """Python type name of output, e.g. 'CodeGraph', 'str', 'dict'."""
    format: str
    """One of: 'graph', 'text', 'json', 'xml', 'dot'."""
    steps_executed: int
    steps: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class CodeGraph:
    def __init__(
        self,
        source_code: str | None = None,
        source_path: str | None = None,
        cpg_path: str | None = None,
    ):
        self.nx_graph = nx.MultiDiGraph()
        # Optional: original source text and path the graph was built from.
        # Used by block-aware trimming/serialization to access line text.
        self.source_code = source_code
        self.source_path = source_path
        # Optional: path to the persisted Joern CPG binary this graph was
        # exported from (see JoernParser(keep_cpg_at=...)). Lets
        # find_taint_flows() reuse it for real interprocedural dataflow
        # queries without re-parsing the source.
        self.cpg_path = cpg_path

    def find_taint_flows(self, source_pattern: str, sink_pattern: str, **kwargs):
        """Run Joern's own interprocedural reachableByFlows against this
        graph's persisted CPG (see `codegraphene.taint.joern_query`).

        Requires `cpg_path` to be set, i.e. this graph came from
        JoernParser(keep_cpg_at=...). Unlike TaintExtractor/ProgramSlicer
        (which traverse the statically exported REACHING_DEF/CDG edges,
        intraprocedural only), this crosses function-call boundaries.
        """
        if not self.cpg_path:
            raise ValueError(
                "This CodeGraph has no persisted CPG (cpg_path is None). "
                "Build it with JoernParser(keep_cpg_at=...) to enable "
                "find_taint_flows() without re-parsing the source."
            )
        from .taint.joern_query import find_taint_flows

        return find_taint_flows(self.cpg_path, source_pattern, sink_pattern, **kwargs)

    def add_node(self, node: Node):
        if node.line_number is None and "LINE_NUMBER" in node.properties:
            try:
                node.line_number = int(node.properties["LINE_NUMBER"])
            except (TypeError, ValueError):
                node.line_number = None
        if node.code is None and "CODE" in node.properties:
            node.code = node.properties["CODE"]
        node_data = {
            "id": node.id,
            "label": node.label,
            "properties": node.properties,
            "code": node.code,
            "line_number": node.line_number,
        }
        self.nx_graph.add_node(node.id, **node_data)

    def add_edge(self, edge: Edge):
        self.nx_graph.add_edge(edge.source, edge.target, label=edge.label)

    def get_edges(self) -> List[Edge]:
        return [Edge(source=u, target=v, label=data.get("label", ""))
                for u, v, data in self.nx_graph.edges(data=True)]

    def get_nodes(self) -> List[Node]:
        return [Node(**data) for _, data in self.nx_graph.nodes(data=True)]

    def get_nodes_by_line(self, line_number: int) -> List[Node]:
        return [node for node in self.get_nodes()
                if NodeGranularity.LINE.extract_line_number(node.properties) == line_number]

    def summary(self) -> str:
        return (
            f"CodeGraph with {self.nx_graph.number_of_nodes()} nodes "
            f"and {self.nx_graph.number_of_edges()} edges."
        )