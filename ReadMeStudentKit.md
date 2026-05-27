# CodeGraphene — Student Kit

This student-focused guide documents the implementation details for Issue #10 and Issue #13, explains why we made the changes, lists the files touched, shows examples to try locally, and provides testing and migration steps.

Audience: junior contributors and students who want to understand the refactor and extend the project.

**Contents**
- Overview
- Issue #10 — explicit modular parameters and pipeline refactor
- Issue #13 — Joern parser enhancements & raw-export short-circuit
- File-by-file changes and rationale
- Usage examples
- Migration notes (old → new)
- Tests and how to run them
- Remaining tasks, trade-offs, and FAQs

---

## Overview

We refactored the pipeline to be more modular, testable, and flexible. The main goals were:

- Make component boundaries explicit (parser, trimmer, serializer) and standardize their interface.
- Make module parameters explicit and discoverable via `describe()` so `dry_run()` can show a plan.
- Support Joern in two modes: (a) graph-building workflow (the default), and (b) raw-export workflow (JSON/XML) where consumers want Joern's artifact directly.
- Preserve backward compatibility for legacy hooks and constructors to avoid breaking existing user scripts.

Two issues drove these changes:

- Issue #10: Make module parameters explicit; introduce `BaseComponent` and `GraphPipeline` with `dry_run()`; update trimmers/serializers accordingly.
- Issue #13: Extend `JoernParser` to accept `source_code` and `language`, add `export_format` including raw `json`/`xml`, add timeouts and robust subprocess handling, and provide efficient short-circuit behavior for raw exports.

---

## Issue #10 — Explicit modular parameters & pipeline refactor

What we implemented

- Introduced `BaseComponent` (in `src/codegraphene/core.py`) as a minimal contract:
  - `run(self, current_graph=None, **context)` — adapter for calling the component.
  - `describe(self)` — returns metadata the pipeline can use for `dry_run()` (name, inputs, outputs, parameters).

- Implemented `GraphPipeline` (in `src/codegraphene/pipeline.py`) that accepts either legacy `parser/trimmer/serializer` args or the new `components=[...]` list.
  - `dry_run(file_path=None, target=None)` shows an ordered plan (each component's `describe()` output).
  - `run(...)` executes components in order and forwards context (first component receives `file_path` or `source_code`, later ones `current_graph` and `target_node_id`).
  - Short-circuit semantics: if a component returns a non-`CodeGraph` value, `run()` returns it immediately.

- Standardized adapters for:
  - Parsers: `BaseParser.run()` uses `build_graph(file_path)` internally.
  - Trimmers: `BaseTrimmer.run()` expects `current_graph` and `target_node_id` and calls `trim(graph, target_node_id)`.
  - Serializers: `BaseSerializer.run()` expects `current_graph` and returns a string.

Why this helps

- Composability: Components are swappable and testable in isolation.
- Safety: `dry_run()` reveals what would run, avoiding accidental Joern calls.
- Testability: We can monkeypatch `run()` or `build_graph()` in unit tests to simulate heavy tools.

Files to inspect for Issue #10

- `src/codegraphene/core.py` — `BaseComponent`, `Node`, `CodeGraph` utilities.
- `src/codegraphene/pipeline.py` — `GraphPipeline`, `dry_run()`, target resolution.
- `src/codegraphene/parsers/base.py` — `BaseParser` adapter.
- `src/codegraphene/trimmers/base.py` — `BaseTrimmer` adapter.
- `src/codegraphene/serializers/base.py` — `BaseSerializer` adapter.


---

## Issue #13 — JoernParser enhancements & raw-export short-circuit

What we implemented

- `JoernParser` (`src/codegraphene/parsers/joern.py`) enhancements:
  - Accepts `source_code` (string) and `language` (e.g., `'c'`, `'cpp'`, `'python'`) for in-memory parsing paths.
  - `export_format` parameter (default `'dot'`) with additional supported values `'json'` and `'xml'` for raw-export modes.
  - Configurable timeouts: `parse_timeout_seconds` and `export_timeout_seconds`.
  - Robust subprocess handling with informative errors on timeout or non-zero exit.
  - For raw-export modes, `build_graph()` (and `run()`) return a `str` containing the raw artifact.
  - Legacy hooks preserved: if an older code path calls `_generate_dot_file()` the hook still functions.

- Pipeline short-circuit behavior:
  - When `JoernParser` returns a non-`CodeGraph` (e.g., a raw JSON string), `GraphPipeline.run()` short-circuits and returns that raw value immediately. The trimmer and serializer are not invoked.

Why short-circuit was added

- Efficiency: If the consumer explicitly requested a raw export (`json`/`xml`), building a NetworkX graph and running trimmers/serializers is wasteful.
- Clear semantics: short-circuit makes it explicit that the pipeline yielded the raw artifact and no further graph processing will occur.
- Testability: Unit tests can simulate the raw-export path without launching Joern.

Important design note

- Default graph workflow remains unchanged. The graph → trim → serialize flow remains the standard path when `export_format='dot'` (the default) and `JoernParser` returns a `CodeGraph`.
- Short-circuit only runs when a component returns a non-`CodeGraph` (opt-in behavior).

Files to inspect for Issue #13

- `src/codegraphene/parsers/joern.py`
- `src/codegraphene/pipeline.py` (short-circuit logic)
- `src/codegraphene/serializers/text.py` (still compatible with graph outputs)


---

## File-by-file change summary (concise)

- `src/codegraphene/core.py` — `BaseComponent` + common types. Small helpers for nodes and CodeGraph.
- `src/codegraphene/pipeline.py` — `GraphPipeline`, `dry_run()`, `run()`, target resolution, legacy-compat glue.
- `src/codegraphene/parsers/base.py` — Base parser adapter.
- `src/codegraphene/parsers/joern.py` — New options `source_code`, `language`, `export_format`, timeouts and robust subprocess handling; raw-export loading.
- `src/codegraphene/trimmers/khop.py` — K-hop trimmer adapted to `BaseTrimmer`'s `run()`.
- `src/codegraphene/serializers/text.py` — `CodeReconstructionSerializer` supports `line_template`, `separator`, and noise filtering.
- `tests/` — unit tests updated and integration tests for Joern remain gated by `RUN_REAL_JOERN=1`.


---

## Usage examples (try these)

1) Standard graph workflow (default)

```python
from codegraphene.core import NodeGranularity
from codegraphene.parsers.joern import JoernParser
from codegraphene.trimmers.khop import KHopTrimmer
from codegraphene.serializers.text import CodeReconstructionSerializer
from codegraphene.pipeline import GraphPipeline

parser = JoernParser(granularity=NodeGranularity.LINE)
trimmer = KHopTrimmer(hops=1)
serializer = CodeReconstructionSerializer(line_template="{line}: {code}")

pipeline = GraphPipeline(components=[parser, trimmer, serializer])

plan = pipeline.dry_run(file_path="examples/sample_code.py", target=42)
print(plan)

out = pipeline.run(file_path="examples/sample_code.py", target=42)
print(out)
```

2) Raw export with short-circuit (Joern JSON)

```python
parser = JoernParser(export_format='json')
pipeline = GraphPipeline(components=[parser])

# returns a JSON string from Joern; pipeline short-circuits and returns str
raw_json = pipeline.run(file_path="examples/sample_code.py")
print(type(raw_json), raw_json[:200])
```

3) In-memory source parsing

```python
source = "int add(int a, int b) { return a + b; }"
parser = JoernParser(source_code=source, language='c')
res = parser.run()  # builds the graph from the in-memory snippet
```


---

## Migration notes (old → new)

Old usage (legacy constructor):

```python
# legacy
pipeline = GraphPipeline(parser=some_parser, trimmer=some_trimmer, serializer=some_serializer)
```

New recommended usage:

```python
pipeline = GraphPipeline(components=[some_parser, some_trimmer, some_serializer])
```

Notes:
- The `GraphPipeline` still accepts legacy `parser=...` for backwards compatibility, but the `components` list is the recommended approach.
- If your code relied on the parser always returning a `CodeGraph`, check places where you may now receive a raw `str` if `export_format` is set to `json`/`xml`.


---

## Tests and how to run them

Run unit tests (Joern not required):

```bash
python -m pytest -q
```

Run Joern-backed tests (requires `joern` on PATH and `RUN_REAL_JOERN=1`):

```bash
export PATH="/path/to/joern/joern-cli/:$PATH"
RUN_REAL_JOERN=1 python -m pytest -q
```

Recommended additional tests (to add):

- `tests/test_pipeline_short_circuit.py` — unit test that monkeypatches `JoernParser.build_graph` to return a `str`, asserts the pipeline returns a `str` and trimmer/serializer are not called.
- `tests/test_integration_joern_raw_export.py` — guarded integration test that calls `JoernParser(export_format='json')` and asserts JSON string returned.

---

## Remaining tasks, trade-offs, and FAQs

Remaining tasks we recommended earlier

- Decide dependency policy for `pydot` / `pyparsing` compatibility. Short-term: pin `pydot==1.4.2`. Long-term: add CI matrix testing.
- Add the two tests above (unit short-circuit + integration raw-export).
- Optionally: demo notebook `examples/demo_for_students.ipynb` and `examples/run_demo.py` to help classroom demos.

Trade-offs

- Short-circuit is opt-in and intentional; it improves efficiency for raw-export users but may surprise consumers expecting a `CodeGraph`. If the team prefers, we can change behavior (e.g., return a file path or parsed object instead of a raw string, or force graph creation via a `force_graph=True` flag).

FAQ — quick answers

Q: Does short-circuit break the pipeline?
A: No — default graph behavior remains intact. Short-circuit triggers only when a component returns a non-`CodeGraph` (e.g., raw JSON), which normally happens when the user explicitly requested raw export.

Q: How do I force graph creation even when `export_format='json'`?
A: We can add a `force_graph=True` option to `JoernParser` to build the graph from the raw artifact; we did not add that by default to keep behavior explicit and efficient.

Q: Where are the key changes located?
A: The primary source files are:
- `src/codegraphene/parsers/joern.py`
- `src/codegraphene/pipeline.py`
- `src/codegraphene/core.py`
- `src/codegraphene/serializers/text.py`


---

## Appendix — quick commands

Run unit tests:

```bash
python -m pytest -q
```

Run guarded Joern tests:

```bash
export PATH="/path/to/joern/joern-cli/:$PATH"
RUN_REAL_JOERN=1 python -m pytest -q
```

---

If you'd like, I can now:
- Add the two recommended tests and run the suite locally.
- Add `examples/run_demo.py` and a short notebook for students.
- Add a `force_graph` option to `JoernParser` if you want raw-export to still be able to produce graphs.

Tell me which of these to do next and I'll proceed.
