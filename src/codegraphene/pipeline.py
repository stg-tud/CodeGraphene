"""GraphPipeline: orchestrates parse → trim → serialize."""

from __future__ import annotations

from typing import Any

import networkx as nx

from .core import BaseComponent, CodeGraph, NodeGranularity, PipelineResult, TargetSpec
from .parsers.base import BaseParser
from .parsers.joern import JoernParser
from .serializers.base import BaseSerializer
from .trimmers.base import BaseTrimmer


def _compose_graphs(graphs: list[CodeGraph]) -> CodeGraph:
    """Union multiple CodeGraphs into one (nodes/edges from all of them)."""
    if len(graphs) == 1:
        return graphs[0]
    result = CodeGraph()
    result.nx_graph = nx.compose_all([g.nx_graph for g in graphs])
    for g in graphs:
        if getattr(g, "source_code", None) is not None:
            result.source_code = g.source_code
            result.source_path = g.source_path
            result.cpg_path = getattr(g, "cpg_path", None)
            break
    return result


class GraphPipeline:
    """Strings together parser, trimmer, and serializer components.

    Args:
        parser: A :class:`BaseParser` implementation for building the graph.
        trimmer: A :class:`BaseTrimmer`, or a list of them to run in
                 sequence -- each trimmer's output feeds the next, so e.g.
                 ``[KHopTrimmer(hops=3), KHopTrimmer(hops=1)]`` progressively
                 narrows the graph. Equivalent to (and implemented via)
                 passing the same trimmers through ``components=``.
        serializer: A :class:`BaseSerializer` implementation for encoding the graph.
        components: Optional ordered list of components to execute.
    """

    def __init__(
        self,
        parser: BaseParser | None = None,
        trimmer: BaseTrimmer | list[BaseTrimmer] | None = None,
        serializer: BaseSerializer | None = None,
        components: list[BaseComponent] | None = None,
    ) -> None:
        self._components: list[BaseComponent] = []
        if components is not None:
            self._components.extend(components)
        else:
            trimmers = trimmer if isinstance(trimmer, list) else [trimmer] if trimmer is not None else []
            for component in (parser, *trimmers, serializer):
                if component is not None:
                    self._components.append(component)

        self._sync_legacy_attributes()

    def add_component(self, component: BaseComponent) -> None:
        """Append a new component to the execution chain."""
        self._components.append(component)
        self._sync_legacy_attributes()

    def components(self) -> list[BaseComponent]:
        """Return a copy of the configured component list."""
        return list(self._components)

    def run(
        self,
        file_path: str | None = None,
        target: TargetSpec | None = None,
        **context: Any,
    ) -> PipelineResult:
        """Execute the full pipeline on *file_path*.

        Args:
            file_path: Path to the input file to parse.
            source_code: Optional raw source text forwarded to the parser.
            language: Optional language hint forwarded to the parser.
            target: Identifies the focal node(s) for trimming. Pass an
                    ``int`` to match by line number, a ``str`` to match by
                    exact label, a compiled ``re.Pattern`` to search
                    label/code, or a ``Callable[[Node], bool]`` predicate.
                    When more than one node matches, each trimmer step runs
                    once per match against the same input graph and the
                    results are unioned -- e.g. tracing every occurrence of
                    a variable or API call at once, not just the first.

        Returns:
            A :class:`PipelineResult` wrapping the final output. The caller
            always receives the same type regardless of whether the pipeline
            completed fully or short-circuited on a raw export.
        """
        current_value: Any = None
        target_node_ids: list[str] = []
        executed_steps: list[str] = []

        for index, component in enumerate(self._components, start=1):
            component_name = component.__class__.__name__
            executed_steps.append(component_name)

            if current_value is None:
                input_label = file_path if file_path is not None else "<source_code>"
                print(f"[Pipeline] Step {index}: running {component_name} on {input_label}...")
                current_value = component.run(file_path=file_path, **context)
            else:
                if not target_node_ids and isinstance(component, BaseTrimmer):
                    raise ValueError("A target node could not be resolved before trimming.")

                print(f"[Pipeline] Step {index}: running {component_name}...")
                if isinstance(component, BaseTrimmer) and len(target_node_ids) > 1:
                    print(
                        f"[Pipeline] {len(target_node_ids)} targets matched; "
                        f"running {component_name} once per target and unioning results."
                    )
                    per_target_results = [
                        component.run(current_graph=current_value, target_node_id=tid, **context)
                        for tid in target_node_ids
                    ]
                    current_value = _compose_graphs(per_target_results)
                else:
                    current_value = component.run(
                        current_graph=current_value,
                        target_node_id=target_node_ids[0] if target_node_ids else None,
                        **context,
                    )

            if isinstance(current_value, CodeGraph) and not target_node_ids and target is not None:
                target_node_ids = self._resolve_target_node_ids(current_value, target)
                print(f"[Pipeline] Target resolved to node(s) {target_node_ids}.")
                
            # Short-circuit: parser returned a raw artifact (e.g. JSON/XML export)
            if index == 1 and not isinstance(current_value, CodeGraph):

                return PipelineResult(
                    output=current_value,
                    kind="joern_export",
                    output_type=type(current_value).__name__,
                    format="raw",
                    steps_executed=index,
                    steps=executed_steps,
                    metadata={"short_circuited": True},
                )

        # Normal completion
        is_str = isinstance(current_value, str)
        return PipelineResult(
            output=current_value,
            kind="serialized_code" if is_str else "codegraph",
            output_type=type(current_value).__name__,
            format="text" if is_str else "graph",
            steps_executed=len(self._components),
            steps=executed_steps,
            metadata={"target_node_ids": target_node_ids} if target_node_ids else {},
        )

    def dry_run(
        self,
        file_path: str | None = None,
        target: TargetSpec | None = None,
    ) -> list[dict[str, Any]]:
        """Describe how the pipeline would execute without running it.

        Issue #10 calls for a safe planning mode so contributors can inspect a
        pipeline before launching heavy external tools like Joern.
        """
        plan = []
        print("[Pipeline] Dry run plan:")
        for index, component in enumerate(self._components, start=1):
            details = component.describe()
            details = {
                "step": index,
                **details,
            }
            plan.append(details)
            print(
                f"  {index}. {details['name']} "
                f"({details['input_type']} -> {details['output_type']})"
            )
        return plan

    def _resolve_target_node_ids(self, graph: CodeGraph, target: TargetSpec) -> list[str]:
        """Resolve a user target to every matching node id."""
        granularity = self._get_granularity()
        target_nodes = granularity.find_target_nodes(graph, target)
        if not target_nodes:
            raise ValueError(
                f"No nodes found matching target {target!r} "
                f"under granularity {granularity.granularity_name!r}"
            )
        return [node.id for node in target_nodes]

    def _get_granularity(self):
        """Extract granularity from the configured parser, or default to LINE."""
        for component in self._components:
            if isinstance(component, JoernParser):
                return component.granularity
            if isinstance(component, BaseParser) and hasattr(component, "granularity"):
                return component.granularity
        return NodeGranularity.LINE

    def _sync_legacy_attributes(self) -> None:
        """Keep the old parser/trimmer/serializer attributes available."""
        self.parser = next(
            (c for c in self._components if isinstance(c, BaseParser)), None
        )
        self.trimmer = next(
            (c for c in self._components if isinstance(c, BaseTrimmer)), None
        )
        self.serializer = next(
            (c for c in reversed(self._components) if isinstance(c, BaseSerializer)),
            None,
        )