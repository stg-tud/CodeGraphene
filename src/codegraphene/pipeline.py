"""GraphPipeline: orchestrates parse → trim → serialize."""

from __future__ import annotations

from typing import Any

from .core import BaseComponent, CodeGraph, NodeGranularity, PipelineResult
from .parsers.base import BaseParser
from .parsers.joern import JoernParser
from .trimmers.base import BaseTrimmer
from .serializers.base import BaseSerializer


class GraphPipeline:
    """Strings together parser, trimmer, and serializer components.

    Args:
        parser: A :class:`BaseParser` implementation for building the graph.
        trimmer: A :class:`BaseTrimmer` implementation for reducing the graph.
        serializer: A :class:`BaseSerializer` implementation for encoding the graph.
        components: Optional ordered list of components to execute.
    """

    def __init__(
        self,
        parser: BaseParser | None = None,
        trimmer: BaseTrimmer | None = None,
        serializer: BaseSerializer | None = None,
        components: list[BaseComponent] | None = None,
    ) -> None:
        self._components: list[BaseComponent] = []
        if components is not None:
            self._components.extend(components)
        else:
            for component in (parser, trimmer, serializer):
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
        target: str | int | None = None,
        **context: Any,
    ) -> PipelineResult:
        """Execute the full pipeline on *file_path*.

        Args:
            file_path: Path to the input file to parse.
            source_code: Optional raw source text forwarded to the parser.
            language: Optional language hint forwarded to the parser.
            target: Identifies the focal node for trimming. Pass an ``int``
                    to match by line number, or a ``str`` to match by label.

        Returns:
            A :class:`PipelineResult` wrapping the final output. The caller
            always receives the same type regardless of whether the pipeline
            completed fully or short-circuited on a raw export.
        """
        current_value: Any = None
        target_node_id: str | None = None
        executed_steps: list[str] = []

        for index, component in enumerate(self._components, start=1):
            component_name = component.__class__.__name__
            executed_steps.append(component_name)

            if current_value is None:
                input_label = file_path if file_path is not None else "<source_code>"
                print(f"[Pipeline] Step {index}: running {component_name} on {input_label}...")
                current_value = component.run(file_path=file_path, **context)
            else:
                if target_node_id is None and isinstance(component, BaseTrimmer):
                    raise ValueError("A target node could not be resolved before trimming.")

                print(f"[Pipeline] Step {index}: running {component_name}...")
                current_value = component.run(
                    current_graph=current_value,
                    target_node_id=target_node_id,
                    **context,
                )

            if isinstance(current_value, CodeGraph) and target_node_id is None:
                target_node_id = self._resolve_target_node_id(current_value, target)
                print(f"[Pipeline] Target resolved to node {target_node_id}.")
                
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
            metadata={},
        )

    def dry_run(
        self,
        file_path: str | None = None,
        target: str | int | None = None,
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

    def _resolve_target_node_id(self, graph: CodeGraph, target: str | int) -> str:
        """Resolve a user target to the first matching node id."""
        granularity = self._get_granularity()
        target_nodes = granularity.find_target_nodes(graph, target)
        if not target_nodes:
            raise ValueError(
                f"No nodes found matching target {target!r} "
                f"under granularity {granularity.granularity_name!r}"
            )
        return target_nodes[0].id

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