"""K-hop neighbourhood trimmer for CodeGraphene."""

from .base import BaseTrimmer
from ..core import CodeGraph


class KHopTrimmer(BaseTrimmer):
    """Trims a :class:`CodeGraph` to the k-hop neighbourhood of a target node.

    Args:
        hops: Number of hops to include around the target node.
    """

    def __init__(self, hops: int) -> None:
        self.hops = hops

    def trim(self, graph: CodeGraph, target_node_id: str) -> CodeGraph:
        """Return the k-hop subgraph centred on *target_node_id*.

        Args:
            graph: The full :class:`CodeGraph` to trim.
            target_node_id: The ID of the focal node.

        Returns:
            A :class:`CodeGraph` containing only nodes (and their connecting
            edges) within *hops* steps of *target_node_id*.

        Note:
            Full k-hop extraction is not yet implemented.
            Currently returns the unmodified graph unchanged.
        """
        # TODO: implement k-hop subgraph extraction using nx.ego_graph
        return graph
