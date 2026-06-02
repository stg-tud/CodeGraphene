from __future__ import annotations

import importlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
from typing import Any, Dict, Iterable, List, Tuple

from ..core import CodeGraph


def _resolve_class(import_path: str):
    module_name, class_name = import_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def _worker_parse(parser_path: str, parser_kwargs: Dict[str, Any], input_spec: Dict[str, Any]) -> CodeGraph:
    """Instantiate the parser inside the worker and parse a single input.

    The input_spec should contain either `file_path` or `source_code` (+ `language`).
    """
    ParserCls = _resolve_class(parser_path)
    parser = ParserCls(**parser_kwargs)
    # Use the same interface as BaseParser.run: accept context dict.
    return parser.run(file_path=input_spec.get("file_path"), source_code=input_spec.get("source_code"), language=input_spec.get("language"))


def parse_many(
    parser_path: str,
    parser_kwargs: Dict[str, Any],
    inputs: Iterable[Dict[str, Any]],
    parallel_workers: int | None = None,
    batch_size: int = 1,
    timeout_per_task: int | None = None,
    stop_on_error: bool = False,
) -> List[Tuple[Dict[str, Any], Any]]:
    """Parse many inputs using a fresh parser instance per worker.

    Returns a list of (input_spec, result) pairs. On success result is a
    :class:`CodeGraph`, on failure it will be the raised Exception instance.
    """
    input_list = list(inputs)
    if parallel_workers is None or parallel_workers < 1:
        parallel_workers = min(4, cpu_count())

    results: List[Tuple[Dict[str, Any], Any]] = []

    # If only one worker requested, run sequentially in-process which makes
    # it easier to unit-test and to avoid pickling/parsing overhead.
    if parallel_workers == 1:
        for spec in input_list:
            try:
                res = _worker_parse(parser_path, parser_kwargs, spec)
            except Exception as exc:  # pragma: no cover - propagation tested
                if stop_on_error:
                    raise
                res = exc
            results.append((spec, res))
        return results

    with ProcessPoolExecutor(max_workers=parallel_workers) as exe:
        futures = {exe.submit(_worker_parse, parser_path, parser_kwargs, spec): spec for spec in input_list}
        for fut in as_completed(futures):
            spec = futures[fut]
            try:
                res = fut.result(timeout=timeout_per_task)
            except Exception as exc:
                res = exc
                if stop_on_error:
                    # Cancel pending futures and raise
                    for f in futures:
                        f.cancel()
                    raise
            results.append((spec, res))

    return results
