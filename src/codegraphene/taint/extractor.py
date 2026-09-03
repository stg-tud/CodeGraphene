"""
TaintExtractor: compute source→sink paths over a CPG's data-dependency edges.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Sequence, Set, Tuple

import networkx as nx

from ..core import CodeGraph, Node, NodeGranularity
from .cwe import CWETemplate, get_template
from .flows import TaintFlow, TaintFlowElement


# Joern's REACHING_DEF edge is the data-dependency edge.
DEFAULT_FLOW_EDGES = ("REACHING_DEF",)

# Joern node label for an incoming method parameter.
PARAM_NODE_LABEL = "METHOD_PARAMETER_IN"

# Joern node label for call sites.
CALL_NODE_LABEL = "CALL"


def _word_bounded_match(text: str, names: Sequence[str]) -> bool:
    """True if any of `names` appears as a word-bounded token in `text`."""
    if not text or not names:
        return False
    pattern = re.compile(r"\b(" + "|".join(re.escape(n) for n in names) + r")\b")
    return pattern.search(text) is not None


class TaintExtractor:
    """Extract taint flows from a CodeGraph using simple DDG path search.

    The extractor identifies source and sink CPG nodes by name (matching the
    NAME or CODE property against a CWE template's lists), then enumerates
    simple paths from any source to any sink along edges whose label is in
    ``flow_edge_types`` (REACHING_DEF by default). Each path becomes a
    TaintFlow.

    Args:
        cwe_id:           CWE identifier; looked up in CWE_TEMPLATES.
        template:         Explicit CWETemplate. Overrides cwe_id if both given.
        source_names:     Explicit source call-name list (overrides template).
        sink_names:       Explicit sink call-name list (overrides template).
        include_parameters_as_sources:
                          If True, treat METHOD_PARAMETER_IN nodes as sources
                          in addition to any named source calls. When None,
                          inherits from the template (default True).
        flow_edge_types:  Edge labels to walk for taint propagation.
        max_path_length:  Cap on simple-path length to keep enumeration cheap.
        max_paths:        Cap on total flows returned.
    """

    def __init__(
        self,
        cwe_id: Optional[str] = None,
        template: Optional[CWETemplate] = None,
        source_names: Optional[Sequence[str]] = None,
        sink_names: Optional[Sequence[str]] = None,
        include_parameters_as_sources: Optional[bool] = None,
        flow_edge_types: Sequence[str] = DEFAULT_FLOW_EDGES,
        max_path_length: int = 20,
        max_paths: int = 64,
    ) -> None:
        if template is None and cwe_id is not None:
            template = get_template(cwe_id)
            if template is None:
                raise ValueError(f"No CWE template for {cwe_id!r}")

        self.template = template
        self.source_names: Tuple[str, ...] = tuple(
            source_names if source_names is not None
            else (template.sources if template else ())
        )
        self.sink_names: Tuple[str, ...] = tuple(
            sink_names if sink_names is not None
            else (template.sinks if template else ())
        )
        if include_parameters_as_sources is None:
            include_parameters_as_sources = (
                template.include_parameters_as_sources if template else True
            )
        self.include_parameters_as_sources = include_parameters_as_sources
        self.flow_edge_types = tuple(flow_edge_types)
        self.max_path_length = max_path_length
        self.max_paths = max_paths

        if not self.sink_names:
            raise ValueError(
                "TaintExtractor needs at least one sink name "
                "(via template, cwe_id, or sink_names)."
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_sources(self, graph: CodeGraph) -> List[Node]:
        """Return CPG nodes that look like taint sources."""
        sources: List[Node] = []
        for node in graph.get_nodes():
            if (
                self.include_parameters_as_sources
                and node.label == PARAM_NODE_LABEL
            ):
                sources.append(node)
                continue
            if self._node_matches_names(node, self.source_names):
                sources.append(node)
        return sources

    def find_sinks(self, graph: CodeGraph) -> List[Node]:
        """Return CPG nodes that look like taint sinks."""
        return [
            node for node in graph.get_nodes()
            if self._node_matches_names(node, self.sink_names)
        ]

    def extract(self, graph: CodeGraph) -> List[TaintFlow]:
        """Find all DDG paths from any source to any sink."""
        sources = self.find_sources(graph)
        sinks = self.find_sinks(graph)
        if not sources or not sinks:
            return []

        ddg_view = self._ddg_view(graph)
        source_ids = {n.id for n in sources}
        sink_ids = {n.id for n in sinks}

        flows: List[TaintFlow] = []
        seen_paths: Set[Tuple[str, ...]] = set()

        for src_id in source_ids:
            if src_id not in ddg_view:
                continue
            for sink_id in sink_ids:
                if sink_id not in ddg_view or sink_id == src_id:
                    continue
                try:
                    paths_iter = nx.all_simple_paths(
                        ddg_view,
                        source=src_id,
                        target=sink_id,
                        cutoff=self.max_path_length,
                    )
                except nx.NodeNotFound:
                    continue

                for path in paths_iter:
                    key = tuple(path)
                    if key in seen_paths:
                        continue
                    seen_paths.add(key)
                    flows.append(self._path_to_flow(graph, path))
                    if len(flows) >= self.max_paths:
                        return flows
        return flows

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _node_matches_names(self, node: Node, names: Sequence[str]) -> bool:
        if not names:
            return False
        # Joern CALL nodes carry NAME (the called function); fall back to CODE.
        name = node.properties.get("NAME")
        if isinstance(name, str) and name in names:
            return True
        code = node.properties.get("CODE", "")
        return _word_bounded_match(code, names)

    def _ddg_view(self, graph: CodeGraph) -> nx.DiGraph:
        """Return a DiGraph view containing only edges in flow_edge_types.

        We collapse the MultiDiGraph to a DiGraph because all_simple_paths is
        much cheaper there and parallel labels don't add new reachability.
        """
        nxg = graph.nx_graph
        view = nx.DiGraph()
        view.add_nodes_from(nxg.nodes(data=True))
        wanted = set(self.flow_edge_types)
        for u, v, data in nxg.edges(data=True):
            if data.get("label") in wanted:
                view.add_edge(u, v)
        return view

    def _path_to_flow(self, graph: CodeGraph, path: Iterable[str]) -> TaintFlow:
        elements: List[TaintFlowElement] = []
        nxg = graph.nx_graph
        for node_id in path:
            props = nxg.nodes[node_id].get("properties", {}) or {}
            line_number = NodeGranularity.LINE.extract_line_number(props)
            line_code = props.get("CODE", "") or ""
            elements.append(
                TaintFlowElement(
                    node_id=node_id,
                    line_number=line_number,
                    line_code=line_code.strip(),
                )
            )
        return TaintFlow(elements=elements)
