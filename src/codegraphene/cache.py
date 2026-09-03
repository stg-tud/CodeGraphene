from __future__ import annotations

import gzip
import json
import os
import pickle
import tempfile
from datetime import datetime

import networkx as nx

from .core import CodeGraph


def _atomic_write_bytes(path: str, data: bytes) -> None:
    dirpath = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=dirpath)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def save_graph(graph: CodeGraph, dest: str, format: str = "auto", overwrite: bool = False) -> str:
    """Save a CodeGraph to `dest`.

    Supported formats: `auto`, `json`, `gpickle`, `gz` (json+gzip).
    If `dest` ends with `.gz` or `format=='gz'`, JSON node-link data will be
    compressed using gzip.
    Returns the path written.
    """
    # Issue #12 asks for a lightweight write/read module first, so local file
    # formats stay simple and deterministic before any hub-specific behavior.
    if os.path.exists(dest) and not overwrite:
        raise FileExistsError(dest)

    if format == "auto":
        if dest.endswith(".gpickle"):
            fmt = "gpickle"
        elif dest.endswith(".gz"):
            fmt = "gz"
        else:
            fmt = "gz"
    else:
        fmt = format

    if fmt == "gpickle":
        # nx.write_gpickle/read_gpickle were removed in networkx>=3.0; the
        # documented replacement is plain pickle of the graph object.
        tmp = dest + ".tmp"
        with open(tmp, "wb") as handle:
            pickle.dump(graph.nx_graph, handle)
        os.replace(tmp, dest)
        return dest

    # Default: node-link JSON, gzip compressed
    data = nx.node_link_data(graph.nx_graph, edges="links")
    payload = json.dumps({"meta": {"created": datetime.utcnow().isoformat()}, "graph": data}).encode("utf-8")
    if fmt == "gz":
        buf = gzip.compress(payload)
        _atomic_write_bytes(dest, buf)
        return dest

    # raw json
    _atomic_write_bytes(dest, payload)
    return dest


def load_graph(src: str) -> CodeGraph:
    """Load a CodeGraph from `src`.

    Detects gzip by extension and uses node-link format for JSON inputs.
    """
    if src.endswith(".gpickle"):
        with open(src, "rb") as handle:
            nx_g = pickle.load(handle)
        cg = CodeGraph()
        cg.nx_graph = nx_g
        return cg

    # read bytes then detect gzip
    with open(src, "rb") as handle:
        raw = handle.read()

    try:
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
    except OSError:
        # not gzip
        pass

    try:
        payload = json.loads(raw.decode("utf-8"))
        node_link = payload.get("graph") or payload
    except Exception:
        raise RuntimeError("Unsupported graph format for file: %s" % src)

    nx_g = nx.node_link_graph(node_link, edges="links")
    cg = CodeGraph()
    cg.nx_graph = nx_g
    return cg


# Optional HuggingFace Datasets integration
try:
    from datasets import Dataset
    _HF_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    _HF_AVAILABLE = False


def _graph_to_gz_bytes(graph: CodeGraph) -> bytes:
    payload = json.dumps(
        {"meta": {"created": datetime.utcnow().isoformat()}, "graph": nx.node_link_data(graph.nx_graph, edges="links")}
    ).encode("utf-8")
    return gzip.compress(payload)


def _gz_bytes_to_graph(data: bytes) -> CodeGraph:
    payload = json.loads(gzip.decompress(data).decode("utf-8"))
    cg = CodeGraph()
    cg.nx_graph = nx.node_link_graph(payload["graph"], edges="links")
    return cg


def save_graph_to_hf(
    graph: CodeGraph | list[CodeGraph],
    dataset_id: str,
    field_name: str = "graph_bytes",
    push_to_hub: bool = False,
    private: bool = False,
    token: str | None = None,
) -> str:
    """Save one or more CodeGraphs into a HuggingFace dataset.

    Args:
        graph: A single :class:`CodeGraph`, or a list of them (one row each,
               since a real corpus is many files, not one).
        dataset_id: A local directory path, or a ``"namespace/name"`` Hub id
                    when ``push_to_hub=True``.
        push_to_hub: If True, push to the Hub instead of ``save_to_disk``.
                     Defaults to False to keep the original local-only
                     behavior as the default.
        private: Passed through to ``Dataset.push_to_hub`` when pushing.
        token: Optional explicit HF auth token; otherwise the ambient
               huggingface-cli login / HF_TOKEN env var is used.

    Returns:
        The dataset_id used (local path or remote id). Requires `datasets`.
    """
    if not _HF_AVAILABLE:
        raise RuntimeError("datasets library is not available. Install with extras 'codegraphene[cache]'.")

    graphs = graph if isinstance(graph, list) else [graph]
    ds = Dataset.from_dict({field_name: [_graph_to_gz_bytes(g) for g in graphs]})

    if push_to_hub:
        ds.push_to_hub(dataset_id, private=private, token=token)
    else:
        ds.save_to_disk(dataset_id)
    return dataset_id


def load_graph_from_hf(
    dataset_id: str,
    field_name: str = "graph_bytes",
    index: int | None = None,
    token: str | None = None,
) -> CodeGraph | list[CodeGraph]:
    """Load CodeGraph(s) previously written by :func:`save_graph_to_hf`.

    Works for both a local ``Dataset.save_to_disk`` directory and a Hub
    dataset id (closes the load-path gap in the original #12 implementation,
    which only supported writing to the HF format, not reading it back).

    Args:
        dataset_id: Local directory path, or a Hub dataset id.
        index: Row to load. If omitted, all rows are returned as a list.
        token: Optional explicit HF auth token for private Hub datasets.

    Returns:
        A single :class:`CodeGraph` if *index* is given, else a list of them.
    """
    if not _HF_AVAILABLE:
        raise RuntimeError("datasets library is not available. Install with extras 'codegraphene[cache]'.")

    if os.path.isdir(dataset_id):
        ds = Dataset.load_from_disk(dataset_id)
    else:
        from datasets import load_dataset

        ds = load_dataset(dataset_id, split="train", token=token)

    if index is not None:
        return _gz_bytes_to_graph(ds[index][field_name])
    return [_gz_bytes_to_graph(row[field_name]) for row in ds]
