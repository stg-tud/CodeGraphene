"""Deterministic JSON serialization of stored graph data."""

import json
import math
from collections.abc import Mapping

import networkx as nx

from ..core import CodeGraph
from .base import BaseSerializer


class GraphJSONSerializer(BaseSerializer):
    """Serialize nodes and directed edges without modifying the graph."""

    def to_dict(self, graph: CodeGraph) -> dict:
        stored_nodes, successors = self._stored_data(graph)
        nodes = []
        ids = {}
        emitted_ids = set()
        fields = {"id", "label", "code", "line_number", "properties"}

        for key, data in stored_nodes.items():
            node_id = self._id(key, f"Node key {key!r}")
            context = f"Node {node_id!r}"
            if not isinstance(data, Mapping) or not fields.issubset(data):
                raise ValueError(f"{context}: incomplete stored model fields")
            stored_id = self._id(data["id"], f"{context}.id")
            if type(key) is not type(data["id"]) or key != data["id"]:
                raise ValueError(f"{context}: node key and stored id disagree")
            if stored_id in emitted_ids:
                raise ValueError(f"{context}: ID collision after string conversion")
            emitted_ids.add(stored_id)
            ids[key] = stored_id

            for field in ("label", "code"):
                if data[field] is not None and type(data[field]) is not str:
                    raise TypeError(f"{context}.{field}: expected str or None")
            if data["line_number"] is not None and type(data["line_number"]) is not int:
                raise TypeError(f"{context}.line_number: expected int or None")
            if type(data["properties"]) is not dict:
                raise TypeError(f"{context}.properties: expected dict")
            nodes.append({
                "id": stored_id,
                "label": data["label"],
                "code": data["code"],
                "line_number": data["line_number"],
                "properties": self._copy_property(
                    data["properties"], f"{context}.properties", set()
                ),
            })

        edges = []
        if successors.keys() != stored_nodes.keys():
            raise ValueError("NetworkX _succ sources disagree with stored nodes")
        for source, targets in successors.items():
            self._id(source, f"Edge source {source!r}")
            if not isinstance(targets, Mapping):
                raise ValueError(f"NetworkX _succ[{source!r}]: expected neighbor mapping")
            for target, keyed_edges in targets.items():
                self._id(target, f"Edge {source!r} target {target!r}")
                if target not in ids:
                    raise ValueError(f"Edge {source!r} -> {target!r}: missing target node")
                if not isinstance(keyed_edges, Mapping) or not keyed_edges:
                    raise ValueError(f"Edge {source!r} -> {target!r}: invalid edge-key mapping")
                for data in keyed_edges.values():
                    context = f"Edge {source!r} -> {target!r}"
                    if not isinstance(data, Mapping) or "label" not in data:
                        raise ValueError(f"{context}: missing stored label")
                    if type(data["label"]) is not str:
                        raise TypeError(f"{context}.label: expected str")
                    edges.append({
                        "source": ids[source], "target": ids[target], "type": data["label"]
                    })

        nodes.sort(key=lambda node: node["id"])
        edges.sort(key=lambda edge: (edge["source"], edge["target"], edge["type"]))
        return {"nodes": nodes, "edges": edges}

    def serialize(self, graph: CodeGraph) -> str:
        return json.dumps(
            self.to_dict(graph),
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )

    @staticmethod
    def _stored_data(graph):
        # Avoid Node.__post_init__ mutations and lazy NetworkX view caches.
        nx_graph = graph.nx_graph
        if not isinstance(nx_graph, nx.MultiDiGraph):
            raise TypeError("Expected a NetworkX MultiDiGraph")
        nodes = getattr(nx_graph, "_node", None)
        successors = getattr(nx_graph, "_succ", None)
        if (
            not isinstance(nodes, Mapping)
            or not isinstance(successors, Mapping)
            or getattr(nx_graph, "_adj", None) is not successors
        ):
            raise ValueError("Incompatible NetworkX _node/_succ/_adj structure")
        return nodes, successors

    @staticmethod
    def _id(value, context):
        if type(value) is str:
            return value
        if type(value) is int:
            return str(value)
        raise TypeError(f"{context}: expected a string or integer ID")

    @classmethod
    def _copy_property(cls, value, path, active):
        value_type = type(value)
        if value is None or value_type in (str, bool, int):
            return value
        if value_type is float:
            if not math.isfinite(value):
                raise ValueError(f"{path}: non-finite float")
            return value
        if value_type not in (list, dict):
            raise TypeError(f"{path}: unsupported property type {value_type.__name__}")
        identity = id(value)
        if identity in active:
            raise ValueError(f"{path}: cyclic container")
        active.add(identity)
        try:
            if value_type is list:
                return [
                    cls._copy_property(item, f"{path}[{index}]", active)
                    for index, item in enumerate(value)
                ]
            result = {}
            for key, item in value.items():
                if type(key) is not str:
                    raise TypeError(f"{path}[{key!r}]: dictionary keys must be strings")
                result[key] = cls._copy_property(item, f"{path}[{key!r}]", active)
            return result
        finally:
            active.remove(identity)
