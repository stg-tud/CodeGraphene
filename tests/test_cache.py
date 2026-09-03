from codegraphene.core import CodeGraph, Edge, Node
from codegraphene.cache import save_graph, load_graph, save_graph_to_hf, load_graph_from_hf
import os


def make_simple_graph():
    cg = CodeGraph()
    # Add a simple node
    cg.add_node(Node(id="n1", label="n1", properties={}))
    return cg


def test_save_load_gz(tmp_path):
    cg = make_simple_graph()
    dest = str(tmp_path / "g.json.gz")
    save_graph(cg, dest, format="gz", overwrite=True)
    assert os.path.exists(dest)
    loaded = load_graph(dest)
    assert isinstance(loaded, CodeGraph)
    assert loaded.nx_graph.number_of_nodes() == cg.nx_graph.number_of_nodes()


def test_save_load_gpickle(tmp_path):
    cg = make_simple_graph()
    dest = str(tmp_path / "g.gpickle")
    save_graph(cg, dest, format="gpickle", overwrite=True)
    assert os.path.exists(dest)
    loaded = load_graph(dest)
    assert isinstance(loaded, CodeGraph)
    assert loaded.nx_graph.number_of_nodes() == cg.nx_graph.number_of_nodes()


def test_save_load_single_graph_to_hf_local(tmp_path):
    cg = make_simple_graph()
    dest = str(tmp_path / "hf_single")
    save_graph_to_hf(cg, dest)
    loaded = load_graph_from_hf(dest, index=0)
    assert isinstance(loaded, CodeGraph)
    assert loaded.nx_graph.number_of_nodes() == cg.nx_graph.number_of_nodes()


def test_save_load_multiple_graphs_to_hf_local(tmp_path):
    cg1 = make_simple_graph()
    cg2 = CodeGraph()
    cg2.add_node(Node(id="n1", label="n1", properties={}))
    cg2.add_node(Node(id="n2", label="n2", properties={}))
    cg2.add_edge(Edge(source="n1", target="n2", label="CFG"))

    dest = str(tmp_path / "hf_multi")
    save_graph_to_hf([cg1, cg2], dest)

    loaded_all = load_graph_from_hf(dest)
    assert len(loaded_all) == 2
    assert loaded_all[0].nx_graph.number_of_nodes() == 1
    assert loaded_all[1].nx_graph.number_of_nodes() == 2
    assert loaded_all[1].nx_graph.number_of_edges() == 1
