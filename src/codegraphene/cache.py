from __future__ import annotations

import gzip
import json
import os
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
        # networkx write_gpickle is atomic enough when writing to tmp and replace
        tmp = dest + ".tmp"
        nx.write_gpickle(graph.nx_graph, tmp)
        os.replace(tmp, dest)
        return dest

    # Default: node-link JSON, gzip compressed
    data = nx.node_link_data(graph.nx_graph)
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
        nx_g = nx.read_gpickle(src)
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

    nx_g = nx.node_link_graph(node_link)
    cg = CodeGraph()
    cg.nx_graph = nx_g
    return cg


# Optional HuggingFace Datasets integration
try:
    from datasets import Dataset
    _HF_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    _HF_AVAILABLE = False


def save_graph_to_hf(graph: CodeGraph, dataset_id: str, field_name: str = "graph_bytes") -> str:
    """Save serialized graph bytes into a HuggingFace dataset as a single-row dataset.

    Returns the dataset_id used (local path or remote id). Requires `datasets`.
    """
    if not _HF_AVAILABLE:
        raise RuntimeError("datasets library is not available. Install with extras 'codegraphene[cache]'.")


    # Issue #12 keeps this as a minimal HF Datasets bridge for now; it stores
    # a single compressed payload locally rather than pushing to the Hub.
    payload = json.dumps({"meta": {"created": datetime.utcnow().isoformat()}, "graph": nx.node_link_data(graph.nx_graph)}).encode("utf-8")
    gz = gzip.compress(payload)
    ds = Dataset.from_dict({field_name: [gz]})
    # Save locally as dataset directory or push if dataset_id looks like a hub path
    ds.save_to_disk(dataset_id)
    return dataset_id
