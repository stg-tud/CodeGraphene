"""Tests for deterministic, mutation-free graph JSON serialization."""

import copy
import json
import os
import subprocess
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

import networkx as nx
import pytest

from codegraphene.core import CodeGraph, Edge, Node, NodeGranularity
from codegraphene.parsers.base import BaseParser
from codegraphene.parsers.joern import JoernParser
from codegraphene.pipeline import GraphPipeline
from codegraphene.serializers import GraphJSONSerializer
from codegraphene.serializers.base import BaseSerializer
from codegraphene.serializers.graph_json import GraphJSONSerializer as DirectSerializer
from codegraphene.trimmers.khop import KHopTrimmer


def _graph():
    graph = CodeGraph(source_code="original", source_path="input.c", cpg_path="cpg.bin")
    for node_id in ("1", "2", "3", "4"):
        graph.add_node(Node(id=node_id, label="MODEL", code="x", line_number=1))
    for source, target, label in (
        ("1", "2", "AST"), ("1", "2", "AST"), ("1", "2", "CFG"),
        ("2", "1", "AST"), ("1", "1", "SELF"), ("2", "3", "CFG"),
        ("3", "4", "CFG"),
    ):
        graph.add_edge(Edge(source=source, target=target, label=label))
    return graph


def _stored_node(graph, key="node", **changes):
    data = dict(id=key, label="MODEL", code=None, line_number=None, properties={})
    data.update(changes)
    graph.nx_graph.add_node(key, **data)
    return graph.nx_graph._node[key]


def _snapshot(graph):
    nx_graph = graph.nx_graph
    values = copy.deepcopy((
        {key: value for key, value in vars(graph).items() if key != "nx_graph"},
        nx_graph.graph, nx_graph._node, nx_graph._succ, nx_graph._pred,
        getattr(nx_graph, "__networkx_cache__", None),
    ))
    identities = set()

    def collect(value):
        identity = id(value)
        if identity in identities:
            return
        identities.add(identity)
        if isinstance(value, dict):
            for key, item in value.items():
                collect(key)
                collect(item)
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                collect(item)

    collect(vars(graph))
    collect(vars(nx_graph))
    attributes = tuple((key, id(value)) for key, value in vars(nx_graph).items())
    return values, identities, attributes


def test_roundtrip_and_exact_fields():
    graph = _graph()
    serializer = GraphJSONSerializer()
    result = serializer.to_dict(graph)
    assert json.loads(serializer.serialize(graph)) == result
    assert set(result) == {"nodes", "edges"}
    assert all(set(node) == {"id", "label", "code", "line_number", "properties"}
               for node in result["nodes"])
    assert all(set(edge) == {"source", "target", "type"} for edge in result["edges"])


def test_model_fields_are_independent_of_properties():
    graph = CodeGraph()
    graph.add_node(Node(
        id="01", label="method name", code="model code", line_number=17,
        properties={"label": "METHOD", "CODE": "property code", "LINE_NUMBER": "003"},
    ))
    node = GraphJSONSerializer().to_dict(graph)["nodes"][0]
    assert node == {
        "id": "01", "label": "method name", "code": "model code", "line_number": 17,
        "properties": {"label": "METHOD", "CODE": "property code", "LINE_NUMBER": "003"},
    }


@pytest.mark.parametrize("label,code,line", [(None, None, None), ("", "", -1), ("x", "", 0)])
def test_preserves_none_empty_and_negative_fields(label, code, line):
    graph = CodeGraph()
    _stored_node(graph, label=label, code=code, line_number=line)
    node = GraphJSONSerializer().to_dict(graph)["nodes"][0]
    assert (node["label"], node["code"], node["line_number"]) == (label, code, line)
    assert node["properties"] == {}


def test_string_and_integer_ids_sort_lexicographically():
    graph = CodeGraph()
    for key in (2, "001", "", -1, 10, "01"):
        _stored_node(graph, key)
    graph.add_edge(Edge(source=-1, target=2, label=""))
    result = GraphJSONSerializer().to_dict(graph)
    assert [node["id"] for node in result["nodes"]] == ["", "-1", "001", "01", "10", "2"]
    assert result["edges"] == [{"source": "-1", "target": "2", "type": ""}]


def test_id_collision_is_rejected():
    graph = CodeGraph()
    _stored_node(graph, 1)
    _stored_node(graph, "1")
    with pytest.raises(ValueError, match="collision"):
        GraphJSONSerializer().serialize(graph)


@pytest.mark.parametrize("key", [True, False, 1.0, ("1",), b"1", None])
def test_unsupported_ids_are_rejected(key):
    graph = CodeGraph()
    _stored_node(graph, key="placeholder")
    # NetworkX itself rejects None keys, so inject the invalid stored state.
    graph.nx_graph._node[key] = graph.nx_graph._node.pop("placeholder")
    with pytest.raises(TypeError, match="ID"):
        GraphJSONSerializer().to_dict(graph)


def test_direction_parallel_edges_types_and_self_edges():
    result = GraphJSONSerializer().to_dict(_graph())
    edges = [(edge["source"], edge["target"], edge["type"]) for edge in result["edges"]]
    assert edges == sorted([
        ("1", "2", "AST"), ("1", "2", "AST"), ("1", "2", "CFG"),
        ("2", "1", "AST"), ("1", "1", "SELF"), ("2", "3", "CFG"),
        ("3", "4", "CFG"),
    ])


def test_determinism_across_node_edge_and_property_insertion_order():
    original = _graph()
    reversed_graph = CodeGraph()
    for key, data in reversed(list(original.nx_graph._node.items())):
        props = {"nested": {"b": 2, "a": 1}, **data["properties"]}
        original.nx_graph._node[key]["properties"] = props
        reverse_props = dict(reversed(list(props.items())))
        reverse_props["nested"] = {"a": 1, "b": 2}
        reversed_graph.nx_graph.add_node(key, **{**data, "properties": reverse_props})
    for source, targets in reversed(list(original.nx_graph._succ.items())):
        for target, keyed_edges in reversed(list(targets.items())):
            for data in reversed(list(keyed_edges.values())):
                reversed_graph.nx_graph.add_edge(source, target, **data)
    serializer = GraphJSONSerializer()
    expected = serializer.serialize(original)
    assert serializer.serialize(original) == expected
    assert serializer.serialize(reversed_graph) == expected
    assert expected == json.dumps(serializer.to_dict(original), sort_keys=True,
                                  ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def test_unicode_quotes_backslashes_and_newlines():
    graph = CodeGraph()
    text = 'Grüße 東京 😀 "quoted" \\path\nnext'
    _stored_node(graph, text, label=text, code=text, properties={text: [text]})
    graph.add_edge(Edge(source=text, target=text, label=text))
    serialized = GraphJSONSerializer().serialize(graph)
    assert "東京 😀" in serialized
    assert json.loads(serialized)["nodes"][0]["properties"] == {text: [text]}
    assert json.loads(serialized)["edges"][0]["type"] == text


@pytest.mark.parametrize("warm_views", [False, True])
def test_no_mutation_of_fields_properties_caches_or_identities(warm_views, monkeypatch):
    graph = _graph()
    shared = {"items": [None, True, 5, -2, 1.25, {"text": "ä"}]}
    for data in graph.nx_graph._node.values():
        data["properties"] = {"left": shared, "right": shared}
    graph.nx_graph.graph["nested"] = {"keep": [1]}
    if warm_views:
        _ = graph.nx_graph.nodes, graph.nx_graph.edges, graph.nx_graph.adj
    monkeypatch.setattr(graph, "get_nodes", lambda: pytest.fail("get_nodes must not be called"))
    before = _snapshot(graph)
    result = GraphJSONSerializer().to_dict(graph)
    GraphJSONSerializer().serialize(graph)
    assert _snapshot(graph) == before
    result["nodes"][0]["properties"]["left"]["items"][5]["text"] = "changed"
    result["nodes"][0]["properties"]["right"]["items"].append("new")
    result["nodes"][0]["label"] = "changed"
    assert _snapshot(graph) == before
    assert result["nodes"][1]["properties"]["left"]["items"] == shared["items"]


@pytest.mark.parametrize("value,exception", [
    (float("nan"), ValueError), (float("inf"), ValueError), (float("-inf"), ValueError),
    ((1, 2), TypeError), ({1, 2}, TypeError), (b"raw", TypeError),
    ({1: "invalid key"}, TypeError), (object(), TypeError),
])
@pytest.mark.parametrize("method", ["to_dict", "serialize"])
def test_invalid_properties_report_node_and_path(value, exception, method):
    graph = CodeGraph()
    _stored_node(graph, "bad-node", properties={"nested": [{"bad": value}]})
    with pytest.raises(exception, match=r"Node 'bad-node'\.properties\['nested'\]\[0\]\['bad'\]"):
        getattr(GraphJSONSerializer(), method)(graph)


@pytest.mark.parametrize("kind", ["list", "dict", "mixed"])
def test_cyclic_properties_are_rejected(kind):
    if kind == "list":
        value = []
        value.append(value)
    else:
        value = {}
        value["cycle"] = value if kind == "dict" else [value]
    graph = CodeGraph()
    _stored_node(graph, properties={"cycle": value})
    with pytest.raises(ValueError, match=r"Node 'node'\.properties.*cyclic"):
        GraphJSONSerializer().serialize(graph)


def test_empty_graph_base_api_export_and_run():
    serializer = GraphJSONSerializer()
    assert DirectSerializer is GraphJSONSerializer
    assert isinstance(serializer, BaseSerializer)
    assert serializer.to_dict(CodeGraph()) == {"nodes": [], "edges": []}
    assert serializer.run(current_graph=CodeGraph()) == '{"edges":[],"nodes":[]}'
    with pytest.raises(ValueError, match="requires a graph"):
        serializer.run()


def test_pipeline_uses_json_string_and_existing_text_format():
    graph = _graph()

    class MemoryParser(BaseParser):
        def build_graph(self, file_path):
            return graph

    before = _snapshot(graph)
    result = GraphPipeline(parser=MemoryParser(), serializer=GraphJSONSerializer()).run(
        file_path="in-memory.c"
    )
    assert result.output == GraphJSONSerializer().serialize(graph)
    assert result.output_type == "str"
    assert result.format == "text"
    assert result.kind == "serialized_code"
    assert result.steps_executed == 2
    assert _snapshot(graph) == before


def test_khop_trimmer_preserves_serializable_model_and_parallel_edges():
    graph = KHopTrimmer(hops=1).trim(_graph(), target_node_id="1")
    before = _snapshot(graph)
    result = json.loads(GraphJSONSerializer().serialize(graph))
    assert [node["id"] for node in result["nodes"]] == ["1", "2"]
    assert len(result["edges"]) == 5
    assert result["edges"].count({"source": "1", "target": "2", "type": "AST"}) == 2
    assert _snapshot(graph) == before


@pytest.mark.parametrize("field", ["id", "label", "code", "line_number", "properties"])
def test_missing_model_fields_are_rejected(field):
    graph = CodeGraph()
    data = _stored_node(graph)
    del data[field]
    before = _snapshot(graph)
    with pytest.raises(ValueError, match="Node 'node'.*incomplete"):
        GraphJSONSerializer().to_dict(graph)
    assert _snapshot(graph) == before


@pytest.mark.parametrize("key,stored_id", [(1, "1"), ("1", 1), ("1", "2")])
def test_conflicting_node_key_and_stored_id(key, stored_id):
    graph = CodeGraph()
    _stored_node(graph, key, id=stored_id)
    with pytest.raises(ValueError, match="disagree"):
        GraphJSONSerializer().serialize(graph)


@pytest.mark.parametrize("field,value", [
    ("id", True), ("label", 3), ("code", []), ("line_number", "3"),
    ("line_number", True), ("properties", None), ("properties", []),
])
def test_invalid_model_field_types(field, value):
    graph = CodeGraph()
    _stored_node(graph, **{field: value})
    with pytest.raises(TypeError, match=field):
        GraphJSONSerializer().to_dict(graph)


def test_edge_created_without_node_model_is_rejected():
    graph = CodeGraph()
    _stored_node(graph)
    graph.add_edge(Edge(source="node", target="missing", label="AST"))
    with pytest.raises(ValueError, match="missing.*incomplete"):
        GraphJSONSerializer().serialize(graph)


@pytest.mark.parametrize("endpoint", [True, 1.0])
def test_edge_endpoint_types_cannot_alias_integer_nodes(endpoint):
    graph = CodeGraph()
    _stored_node(graph, 1)
    _stored_node(graph, "source")
    graph.add_edge(Edge(source="source", target=endpoint, label="AST"))
    with pytest.raises(TypeError, match="target.*ID"):
        GraphJSONSerializer().to_dict(graph)


@pytest.mark.parametrize("data,exception", [({}, ValueError), ({"label": None}, TypeError)])
def test_invalid_edge_model(data, exception):
    graph = CodeGraph()
    _stored_node(graph)
    graph.nx_graph.add_edge("node", "node", **data)
    with pytest.raises(exception, match="Edge.*label"):
        GraphJSONSerializer().to_dict(graph)


def test_networkx_internal_layout_matches_public_graph_data():
    graph = _graph()
    raw = graph.nx_graph
    assert isinstance(raw._node, Mapping)
    assert raw._adj is raw._succ
    assert raw._succ.keys() == raw._node.keys()
    expected = Counter((u, v, data["label"]) for u, v, _, data in raw.edges(keys=True, data=True))
    for source, targets in raw._succ.items():
        assert isinstance(targets, Mapping)
        for target, keyed_edges in targets.items():
            assert keyed_edges is raw._pred[target][source]
            assert isinstance(keyed_edges, Mapping)
            assert all(isinstance(data, Mapping) for data in keyed_edges.values())
    before = _snapshot(graph)
    result = GraphJSONSerializer().to_dict(graph)
    assert {node["id"] for node in result["nodes"]} == set(raw._node)
    assert Counter((e["source"], e["target"], e["type"]) for e in result["edges"]) == expected
    assert _snapshot(graph) == before


@pytest.mark.parametrize("corruption", [
    "node_mapping", "succ_mapping", "adj_alias", "sources", "neighbors",
    "target", "edge_keys", "empty_edge_keys", "edge_data",
])
def test_incompatible_networkx_internals_fail_explicitly(corruption):
    graph = _graph()
    raw = graph.nx_graph
    if corruption == "node_mapping":
        raw._node = []
    elif corruption == "succ_mapping":
        raw._succ = []
    elif corruption == "adj_alias":
        raw.__dict__["_adj"] = {}
    elif corruption == "sources":
        raw._succ["missing"] = {}
    elif corruption == "neighbors":
        raw._succ["1"] = []
    elif corruption == "target":
        raw._succ["1"]["missing"] = {0: {"label": "AST"}}
    elif corruption == "edge_keys":
        raw._succ["1"]["2"] = []
    elif corruption == "empty_edge_keys":
        raw._succ["1"]["2"] = {}
    else:
        raw._succ["1"]["2"][0] = []
    with pytest.raises(ValueError):
        GraphJSONSerializer().to_dict(graph)


@pytest.mark.parametrize("raw", [nx.Graph(), nx.DiGraph(), nx.MultiGraph()])
def test_incompatible_networkx_graph_type(raw):
    graph = CodeGraph()
    graph.nx_graph = raw
    with pytest.raises(TypeError, match="MultiDiGraph"):
        GraphJSONSerializer().to_dict(graph)


@pytest.mark.integration
def test_real_p2_dot_serialization(monkeypatch):
    configured_path = os.environ.get("GRAPHJSON_P2_DOT")
    if not configured_path:
        pytest.skip("Set GRAPHJSON_P2_DOT to an existing P2 DOT export")
    path = Path(configured_path)
    assert path.is_file(), f"DOT evidence not found: {path}"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("No parser processes"))
    graph = JoernParser(granularity=NodeGranularity.RAW)._load_graph_from_dot(str(path))
    raw = graph.nx_graph
    expected = Counter((u, v, data["label"]) for u, v, data in raw.edges(data=True))
    before = _snapshot(graph)
    serializer = GraphJSONSerializer()
    result = serializer.to_dict(graph)
    assert json.loads(serializer.serialize(graph)) == result
    assert len(result["nodes"]) == len(raw._node)
    actual = Counter((e["source"], e["target"], e["type"]) for e in result["edges"])
    parallel_pairs = Counter((e["source"], e["target"]) for e in result["edges"])
    assert actual == expected
    assert sum(actual.values()) == sum(expected.values())
    assert sum(count - 1 for count in actual.values()) == sum(count - 1 for count in expected.values())
    for node in result["nodes"]:
        assert node["properties"] == raw._node[node["id"]]["properties"]
    assert _snapshot(graph) == before
    print(f"P2 DOT: {path}; nodes={len(result['nodes'])}; edges={sum(actual.values())}; "
          f"parallel pairs={sum(count > 1 for count in parallel_pairs.values())}; "
          f"parallel excess={sum(count - 1 for count in parallel_pairs.values())}; "
          f"duplicate triples={sum(count - 1 for count in actual.values())}")
