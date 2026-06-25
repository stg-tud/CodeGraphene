"""
TaintFlowTrimmer: trims a CPG to nodes covered by source→sink taint flows.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

import networkx as nx

from ..core import CodeGraph, Edge, Node
from ..taint.cwe import CWETemplate
from ..taint.extractor import TaintExtractor
from ..taint.flows import TaintFlow
from .base import BaseTrimmer


class TaintFlowTrimmer(BaseTrimmer):
    """Reduce a CodeGraph to the union of nodes covered by taint flows.

    Internally delegates to TaintExtractor. The ``target_node_id`` passed by
    GraphPipeline is treated as an extra anchor: it is always included in the
    result. When no flows are found, the trimmer returns only the flow-derived
    slice (possibly just the target alone).

    Args:
        cwe_id:          CWE id to load a template for. Mutually substitutable
                         with ``template``, ``source_names``/``sink_names``,
                         or an explicit ``extractor``.
        template:        Explicit CWETemplate (overrides ``cwe_id``).
        source_names:    Explicit source name list.
        sink_names:      Explicit sink name list.
        extractor:       Pre-built TaintExtractor. Overrides everything else.
        context_hops:    Optional k-hop padding around every flow node, over
                         the full graph (any edge type). 0 disables padding.
        include_target:  If True, include the pipeline's target node and
                         (when context_hops > 0) its neighbourhood as well.
    """

    def __init__(
        self,
        cwe_id: Optional[str] = None,
        template: Optional[CWETemplate] = None,
        source_names: Optional[Sequence[str]] = None,
        sink_names: Optional[Sequence[str]] = None,
        extractor: Optional[TaintExtractor] = None,
        context_hops: int = 0,
        include_target: bool = True,
    ) -> None:
        if extractor is None:
            extractor = TaintExtractor(
                cwe_id=cwe_id,
                template=template,
                source_names=source_names,
                sink_names=sink_names,
            )
        self.extractor = extractor
        self.context_hops = context_hops
        self.include_target = include_target
        self._last_flows: List[TaintFlow] = []

    @property
    def last_flows(self) -> List[TaintFlow]:
        """The flows produced by the most recent ``trim`` call."""
        return self._last_flows

    def trim(self, graph: CodeGraph, target_node_id: str) -> CodeGraph:
        flows = self.extractor.extract(graph)
        self._last_flows = flows

        keep_ids: set[str] = set()
        for flow in flows:
            keep_ids.update(flow.node_ids)

        if self.include_target and target_node_id in graph.nx_graph:
            keep_ids.add(target_node_id)

        if not keep_ids:
            return CodeGraph(source_code=graph.source_code, source_path=graph.source_path)

        if self.context_hops > 0:
            keep_ids = self._expand_neighbourhood(graph, keep_ids, self.context_hops)

        return self._induced_subgraph(graph, keep_ids)

    # ------------------------------------------------------------------

    def _expand_neighbourhood(
        self,
        graph: CodeGraph,
        seed_ids: set[str],
        radius: int,
    ) -> set[str]:
        nxg = graph.nx_graph
        expanded: set[str] = set(seed_ids)
        for nid in seed_ids:
            if nid not in nxg:
                continue
            ego = nx.ego_graph(nxg, nid, radius=radius, undirected=True)
            expanded.update(ego.nodes())
        return expanded

    def _induced_subgraph(self, graph: CodeGraph, node_ids: set[str]) -> CodeGraph:
        nxg = graph.nx_graph
        out = CodeGraph(source_code=graph.source_code, source_path=graph.source_path)
        for nid in node_ids:
            if nid not in nxg:
                continue
            data = nxg.nodes[nid]
            out.add_node(Node(**data))
        for u, v, data in nxg.edges(data=True):
            if u in node_ids and v in node_ids:
                out.add_edge(Edge(source=u, target=v, label=data.get("label", "")))
        return out
