from codegraphene.core import CodeGraph, Node
from codegraphene.cache import save_graph, load_graph
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
