import os
import json
import subprocess
import tempfile
from pathlib import Path

import networkx as nx

from .base import BaseParser
from ..core import CodeGraph, Node, Edge, NodeGranularity

class JoernParser(BaseParser):
    def __init__(
        self,
        joern_path: str = "joern",
        granularity: NodeGranularity = NodeGranularity.LINE,
        export_format: str = "dot",
        parse_timeout_seconds: int = 120,
        export_timeout_seconds: int = 120,
    ) -> None:
        """
        :param joern_path:   The command or path to the Joern executable.
        :param granularity:  Controls which CPG nodes are included and how they
                             are labelled. Defaults to NodeGranularity.LINE.
        """
        self.joern_path = joern_path
        self.granularity = granularity
        self.export_format = export_format
        self.parse_timeout_seconds = parse_timeout_seconds
        self.export_timeout_seconds = export_timeout_seconds

    def run(self, current_graph=None, **context):
        """Execute Joern parsing with file-path or raw-source inputs."""
        file_path = context.get("file_path")
        source_code = context.get("source_code")
        language = context.get("language")

        # A Cleaner upstream may have produced cleaned source text and passed it
        # forward as current_graph. Use it if no explicit source_code was given.
        if source_code is None and isinstance(current_graph, str):
            source_code = current_graph
            if language is None and file_path and "." in file_path:
                language = file_path.rsplit(".", 1)[-1]
            file_path = None

        if not file_path and not source_code:
            raise ValueError("JoernParser.run() requires 'file_path' or 'source_code'.")

        return self.build_graph(file_path=file_path, source_code=source_code, language=language)

    def build_graph(
        self,
        file_path: str | None = None,
        source_code: str | None = None,
        language: str | None = None,
    ):
        input_description = file_path or f"<source_code:{language or 'unknown'}>"
        print(f"[JoernParser] Parsing source code at: {input_description}")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            resolved_file_path = self._prepare_input_path(
                file_path=file_path,
                source_code=source_code,
                language=language,
                temp_dir=temp_dir,
            )
            # Issue #13 requires this parser to support raw exports as an
            # explicit opt-in path instead of always forcing a CodeGraph.
            export_artifact = self._generate_dot_file(resolved_file_path, temp_dir)
            
            if self.export_format == "dot":
                return self._load_graph_from_dot(export_artifact)
                
            # --- PHASE 1: JSON CONTRACT LOGIC ---
            if self.export_format == "json":
                try:
                    return json.loads(export_artifact)
                except json.JSONDecodeError as e:
                    snippet = str(export_artifact)[:250]
                    raise ValueError(f"JSON Decode Error: {e}\nRaw output snippet: {snippet}...")
                    
            return export_artifact

    def describe(self) -> dict:
        info = super().describe()
        info.update(
            {
                "name": "JoernParser",
                "granularity": self.granularity.granularity_name,
                "capabilities": ["read_file", "spawn_process"],
                "input_type": "file_path | source_code",
                "output_type": "CodeGraph" if self.export_format == "dot" else "dict" if self.export_format == "json" else "str",
                "input_modes": ["file_path", "source_code"],
                "export_format": self.export_format,
                "parse_timeout_seconds": self.parse_timeout_seconds,
                "export_timeout_seconds": self.export_timeout_seconds,
            }
        )
        return info

    # ------------------------------------------------------------------
    # DOT generation
    # ------------------------------------------------------------------
    def _prepare_input_path(
        self,
        file_path: str | None,
        source_code: str | None,
        language: str | None,
        temp_dir: str,
    ) -> str:
        if source_code is None:
            if file_path is None:
                raise ValueError("JoernParser requires either 'file_path' or 'source_code'.")
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Input file does not exist: {file_path}")
            return file_path

        if not language:
            raise ValueError("JoernParser requires 'language' when 'source_code' is provided.")

        extension = self._language_to_extension(language)
        source_file_path = os.path.join(temp_dir, f"input.{extension}")
        with open(source_file_path, "w", encoding="utf-8") as handle:
            handle.write(source_code)
        return source_file_path

    def _language_to_extension(self, language: str) -> str:
        mapping = {
            "python": "py",
            "py": "py",
            "java": "java",
            "javascript": "js",
            "js": "js",
            "typescript": "ts",
            "ts": "ts",
            "c": "c",
            "cpp": "cpp",
            "c++": "cpp",
            "go": "go",
            "ruby": "rb",
            "rb": "rb",
            "php": "php",
            "kotlin": "kt",
            "kt": "kt",
            "swift": "swift",
            "scala": "scala",
            "csharp": "cs",
            "cs": "cs",
        }
        return mapping.get(language.lower(), language.lower().lstrip(".")) or "txt"

    def _generate_export_artifact(self, file_path: str, temp_dir: str) -> str:
        """Run joern-parse and joern-export, returning either a DOT path or raw artifact."""
        cpg_out    = os.path.join(temp_dir, "cpg.bin")
        export_out = os.path.join(temp_dir, "export")

        self._run_joern_parse(file_path, cpg_out)
        self._run_joern_export(cpg_out, export_out)

        if self.export_format != "dot":
            # Keep the raw export path visible so notebooks and downstream tools
            # can inspect Joern's native artifact without rebuilding a graph.
            raw_artifact = self._load_raw_export_artifact(export_out)
            if raw_artifact is not None:
                return raw_artifact
            return export_out

        dot_file_path = os.path.join(export_out, "export.dot")
        if not os.path.exists(dot_file_path):
            raise FileNotFoundError(
                f"Joern failed to generate the DOT file at {dot_file_path}"
            )
        return dot_file_path

    def _generate_dot_file(self, file_path: str, temp_dir: str) -> str:
        """Backward-compatible hook for tests and existing monkeypatches."""
        return self._generate_export_artifact(file_path, temp_dir)

    def _run_joern_parse(self, file_path: str, cpg_out: str) -> None:
        """Invoke joern-parse to produce a CPG binary."""
        cmd = [f"{self.joern_path}-parse", file_path, "--output", cpg_out]
        print(f"[JoernParser] Running: {' '.join(cmd)}")
        self._run_command(cmd, timeout_seconds=self.parse_timeout_seconds, step_name="joern-parse")

    def _run_joern_export(self, cpg_out: str, export_out: str) -> None:
        """Invoke joern-export to produce a DOT file from the CPG binary."""
        repr_name = "all" if self.export_format == "dot" else self.export_format
        cmd = [f"{self.joern_path}-export", cpg_out, "--repr", repr_name, "--out", export_out]
        print(f"[JoernParser] Running: {' '.join(cmd)}")
        self._run_command(cmd, timeout_seconds=self.export_timeout_seconds, step_name="joern-export")

    def _load_raw_export_artifact(self, export_out: str) -> str | None:
        matches = list(Path(export_out).rglob(f"*.{self.export_format}"))
        if not matches:
            return None
        artifact_path = matches[0]
        try:
            return artifact_path.read_text(encoding="utf-8")
        except OSError:
            return str(artifact_path)

    def _run_command(self, cmd: list[str], timeout_seconds: int, step_name: str) -> None:
        """Run a subprocess command with timeout and clear error messages."""
        try:
            subprocess.run(
                cmd,
                check=True,
                timeout=timeout_seconds,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"{step_name} command not found. Ensure Joern is installed and PATH is configured."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"{step_name} timed out after {timeout_seconds}s while processing input."
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            stdout = (exc.stdout or "").strip()
            details = stderr if stderr else stdout
            if len(details) > 400:
                details = details[:400] + "..."
            message = f"{step_name} failed with exit code {exc.returncode}."
            if details:
                message += f" Details: {details}"
            raise RuntimeError(message) from exc

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------
    def _load_graph_from_dot(self, dot_file_path: str) -> CodeGraph:
        """Parse a DOT file into a CodeGraph using the configured granularity."""
        print("[JoernParser] Ingesting DOT file into NetworkX...")
        raw_nx_graph = nx.drawing.nx_pydot.read_dot(dot_file_path)
        code_graph = CodeGraph()

        self._add_nodes(raw_nx_graph, code_graph)
        self._add_edges(raw_nx_graph, code_graph)

        return code_graph

    def _add_nodes(self, raw_nx_graph: nx.Graph, code_graph: CodeGraph) -> None:
        for node_id, data in raw_nx_graph.nodes(data=True):
            node = self._parse_node(node_id, data)
            if node is not None:
                code_graph.add_node(node)

    def _parse_node(self, node_id: str, data: dict) -> Node | None:
        """Return a Node if the data satisfies the current granularity, else None."""
        clean_data = {
            k: v.strip('"') if isinstance(v, str) else v
            for k, v in data.items()
        }
        if not self.granularity.is_valid(clean_data):
            return None

        # Preserve historical behavior used by tests for malformed line numbers.
        line_number = self.granularity.extract_line_number(clean_data)
        if self.granularity.line_attr is not None and line_number is None:
            line_number = -1

        return Node(
            id=node_id,
            label=self.granularity.extract_label(clean_data),
            properties=clean_data,
            code=self.granularity.extract_code(clean_data),
            line_number=line_number,
        )

    def _add_edges(self, raw_nx_graph: nx.Graph, code_graph: CodeGraph) -> None:
        valid_node_ids = set(code_graph.nx_graph.nodes())
        for u, v, data in raw_nx_graph.edges(data=True):
            if u in valid_node_ids and v in valid_node_ids:
                clean_label = data.get("label", '""').strip('"')
                code_graph.add_edge(Edge(source=u, target=v, label=clean_label))