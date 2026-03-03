import os
import subprocess
import tempfile
import networkx as nx

from .base import BaseParser
from ..core import CodeGraph, Node, Edge


class JoernParser(BaseParser):
    def __init__(self, joern_path: str = "joern"):
        """
        :param joern_path: The command or path to the Joern executable. 
                           Defaults to 'joern' assuming it's in your PATH.
        """
        self.joern_path = joern_path

    def build_graph(self, file_path: str) -> CodeGraph:
        print(f"[JoernParser] Parsing source code at: {file_path}")

        with tempfile.TemporaryDirectory() as temp_dir:
            dot_file_path = self._generate_dot_file(file_path, temp_dir)
            return self._load_graph_from_dot(dot_file_path)

    def _generate_dot_file(self, file_path: str, temp_dir: str) -> str:
        """Run joern-parse and joern-export, returning the path to the generated DOT file."""
        cpg_out = os.path.join(temp_dir, "cpg.bin")
        export_out = os.path.join(temp_dir, "export")

        self._run_joern_parse(file_path, cpg_out)
        self._run_joern_export(cpg_out, export_out)

        dot_file_path = os.path.join(export_out, "export.dot")
        if not os.path.exists(dot_file_path):
            raise FileNotFoundError(f"Joern failed to generate the DOT file at {dot_file_path}")

        return dot_file_path

    def _run_joern_parse(self, file_path: str, cpg_out: str) -> None:
        """Invoke joern-parse to produce a CPG binary."""
        cmd = [f"{self.joern_path}-parse", file_path, "--output", cpg_out]
        print(f"[JoernParser] Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _run_joern_export(self, cpg_out: str, export_out: str) -> None:
        """Invoke joern-export to produce a DOT file from the CPG binary."""
        cmd = [f"{self.joern_path}-export", cpg_out, "--repr", "all", "--out", export_out]
        print(f"[JoernParser] Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _load_graph_from_dot(self, dot_file_path: str) -> CodeGraph:
        """Parse a DOT file into a CodeGraph, filtering and cleaning nodes and edges."""
        print(f"[JoernParser] Ingesting DOT file into NetworkX...")
        raw_nx_graph = nx.drawing.nx_pydot.read_dot(dot_file_path)

        code_graph = CodeGraph()
        self._add_nodes(raw_nx_graph, code_graph)
        self._add_edges(raw_nx_graph, code_graph)
        return code_graph

    def _add_nodes(self, raw_nx_graph: nx.Graph, code_graph: CodeGraph) -> None:
        """Clean, filter, and add nodes from a raw NetworkX graph into a CodeGraph."""
        for node_id, data in raw_nx_graph.nodes(data=True):
            node = self._parse_node(node_id, data)
            if node is not None:
                code_graph.add_node(node)

    def _parse_node(self, node_id: str, data: dict) -> Node | None:
        """Convert raw node data into a Node, returning None if the node should be excluded."""
        clean_data = {k: v.strip('"') if isinstance(v, str) else v for k, v in data.items()}

        if 'LINE_NUMBER' not in clean_data or 'CODE' not in clean_data:
            return None

        try:
            line_num = int(clean_data['LINE_NUMBER'])
        except ValueError:
            line_num = -1

        return Node(
            id=node_id,
            label=clean_data.get('label', 'UNKNOWN'),
            code=clean_data['CODE'],
            line_number=line_num,
            properties=clean_data,
        )

    def _add_edges(self, raw_nx_graph: nx.Graph, code_graph: CodeGraph) -> None:
        """Clean and add edges, skipping any that reference nodes absent from the CodeGraph."""
        valid_node_ids = set(code_graph.nx_graph.nodes())

        for u, v, data in raw_nx_graph.edges(data=True):
            if u in valid_node_ids and v in valid_node_ids:
                clean_label = data.get('label', '""').strip('"')
                code_graph.add_edge(Edge(source=u, target=v, label=clean_label))