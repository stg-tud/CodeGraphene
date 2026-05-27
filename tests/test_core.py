"""Tests for the core data structures and abstract parser interface."""

import pytest

from codegraphene.core import CodeGraph, Node, Edge, NodeGranularity


# Basic tests for core data structures and abstract parser interface
class TestCoreDataStructures:
    """Unit tests for Node, Edge, and CodeGraph."""

    # Test Node and Edge creation
    def test_node_and_edge_creation(self):
        node = Node(id="1", label="TEST_NODE", properties={"key": "value"})
        edge = Edge(source="1", target="2", label="TEST_EDGE")
        assert node.id == "1"
        assert node.label == "TEST_NODE"
        assert node.properties["key"] == "value"
        assert edge.source == "1"
        assert edge.target == "2"
        assert edge.label == "TEST_EDGE"

    # Test NodeGranularity methods for all granularity types
    def test_node_granularity_methods(self):
        line_node = Node(
            id="1", label="ASSIGN", properties={"LINE_NUMBER": "10", "CODE": "x = 1"}
        )
        method_node = Node(
            id="2",
            label="myMethod",
            properties={"NAME": "myMethod", "FULL_NAME": "com.example.myMethod"},
        )
        file_node = Node(
            id="3", label="MyFile.java", properties={"NAME": "MyFile.java"}
        )

        assert NodeGranularity.LINE.is_valid(line_node.properties)
        assert NodeGranularity.LINE.extract_label(line_node.properties) == "ASSIGN"
        assert NodeGranularity.LINE.extract_code(line_node.properties) == "x = 1"
        assert NodeGranularity.LINE.extract_line_number(line_node.properties) == 10

        assert NodeGranularity.METHOD.is_valid(method_node.properties)
        assert (
            NodeGranularity.METHOD.extract_label(method_node.properties) == "myMethod"
        )
        assert (
            NodeGranularity.METHOD.extract_code(method_node.properties)
            == "com.example.myMethod"
        )
        assert (
            NodeGranularity.METHOD.extract_line_number(method_node.properties) is None
        )

        assert NodeGranularity.FILE.is_valid(file_node.properties)
        assert NodeGranularity.FILE.extract_label(file_node.properties) == "MyFile.java"
        assert NodeGranularity.FILE.extract_code(file_node.properties) == "MyFile.java"
        assert NodeGranularity.FILE.extract_line_number(file_node.properties) is None

    # Test CodeGraph node and edge addition
    def test_codegraph_add_node_and_edge(self):
        graph = CodeGraph()
        node = Node(id="1", label="TEST_NODE", properties={"key": "value"})
        edge = Edge(source="1", target="2", label="TEST_EDGE")
        graph.add_node(node)
        graph.add_edge(edge)
        assert graph.nx_graph.number_of_nodes() == 1
        assert graph.nx_graph.number_of_edges() == 1
        # Verify that the node data is stored correctly
        stored_node_data = graph.nx_graph.nodes["1"]
        assert stored_node_data["id"] == "1"
        assert stored_node_data["label"] == "TEST_NODE"
        assert stored_node_data["properties"]["key"] == "value"
        # Verify that the edge data is stored correctly        stored_edge_data = graph.nx_graph.get_edge_data("1", "2")
        assert graph.nx_graph.has_edge("1", "2")
        stored_edge_data = graph.nx_graph.get_edge_data("1", "2")
        assert stored_edge_data is not None
        # Since it's a MultiDiGraph, get_edge_data returns a dict of dicts keyed by edge keys
        edge_data = list(stored_edge_data.values())[0]
        assert edge_data["label"] == "TEST_EDGE"

    # Test CodeGraph summary and get_nodes_by_line
    def test_codegraph_methods(self):
        graph = CodeGraph()
        assert graph.summary() == "CodeGraph with 0 nodes and 0 edges."
        node1 = Node(id="1", label="NODE1", properties={"LINE_NUMBER": "10"})
        node2 = Node(id="2", label="NODE2", properties={"LINE_NUMBER": "20"})
        edge = Edge(source="1", target="2", label="TEST_EDGE")
        graph.add_node(node1)
        graph.add_node(node2)
        graph.add_edge(edge)
        assert graph.summary() == "CodeGraph with 2 nodes and 1 edges."
        # add get_nodes as well
        nodes = graph.get_nodes()
        assert len(nodes) == 2
        assert any(node.id == "1" and node.label == "NODE1" for node in nodes)
        assert any(node.id == "2" and node.label == "NODE2" for node in nodes)
        # test get_nodes_by_line
        nodes_by_line_10 = graph.get_nodes_by_line(10)
        assert len(nodes_by_line_10) == 1
        assert nodes_by_line_10[0].id == "1"
        assert nodes_by_line_10[0].label == "NODE1"
        assert nodes_by_line_10[0].properties["LINE_NUMBER"] == "10"