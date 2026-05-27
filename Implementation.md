# Implementation Decisions — Issues #10 & #13


## Goals and guiding principles

Primary goals that drove the implementation:

- Make component boundaries explicit and discoverable so contributors can add/replace parts easily.
- Make the pipeline safe to inspect (`dry_run`) and to unit-test without launching heavy external tools (Joern).
- Preserve backward compatibility so existing scripts and tests don't break immediately.
- Support two useful workflows: a full graph → trim → serialize flow, and a raw-export flow (Joern JSON/XML) for tooling.

Design principles applied:

- Single Responsibility: each component (parser, trimmer, serializer) is responsible for one clear job.
- Adapter pattern: each concrete module exposes the same small `run()` adapter so the pipeline can call components uniformly.
- Explicit opt-in behavior: changes that would alter behavior (like returning raw artifacts) are opt-in (via `export_format`).
- Fail-fast and observable: `dry_run()` plus clear errors/timeouts reduce accidental expensive operations in CI.

---

## High-level architecture (before vs after)

Before
- Pipeline had special-case wiring between parser, trimmer, and serializer.
- Parser implementations often had different entry points and signatures.
- Tests or developers sometimes invoked Joern during experimentation.

After
- Introduced `BaseComponent` contract (`run()` + `describe()`).
- `GraphPipeline(components=[...])` composes arbitrary components; legacy constructor compatibility preserved.
- `dry_run()` uses `describe()` metadata to show planned steps without execution.
- `JoernParser` accepts `source_code` / `language` and `export_format` (dot/json/xml) and can return raw artifacts.



## Issue #10 — Make module parameters explicit and refactor pipeline

What changed
1. Added `BaseComponent` in `src/codegraphene/core.py` requiring a `run(self, current_graph=None, **context)` adapter and `describe()` metadata.
2. Implemented `GraphPipeline` in `src/codegraphene/pipeline.py` which accepts `components=[...]` or the legacy `parser=.., trimmer=.., serializer=..` arguments.
3. Implemented adapters in `BaseParser`, `BaseTrimmer`, `BaseSerializer` so existing modules conform to the new contract.
4. Added `dry_run()` to allow safe inspection of the pipeline plan.

Why this design
- Uniform interfaces simplify composing different modules and writing tests.
- `describe()` separates introspection from execution: dry-run tooling can safely query components about their needs and outputs.
- Legacy compatibility avoids breaking existing workflows immediately while migrating to the new model.

How it was implemented (step-by-step)
- Step 1: Define `BaseComponent` with two required methods:
  - `run(self, current_graph=None, **context)` — a tiny, consistent adapter used at runtime.
  - `describe(self)` — returns a dictionary with fields like `name`, `input_type`, `output_type`, and `params`.

- Step 2: Update parser/trimmer/serializer base classes to implement `BaseComponent`:
  - `BaseParser` implements `run()` by calling `build_graph(file_path)`.
  - `BaseTrimmer` implements `run()` by requiring `current_graph` and `target_node_id` and calling `trim()`.
  - `BaseSerializer` implements `run()` by requiring `current_graph` and returning a textual serialization.

- Step 3: Implement `GraphPipeline` sequencing logic:
  - Accepts `components` list, normalizes legacy args to `components` internally.
  - `dry_run()` iterates `components` calling `describe()` to assemble a plan.
  - `run()` iteratively calls component.run(); after the first `CodeGraph` is observed, the pipeline resolves `target_node_id` and forwards it to subsequent components.
  - If a component returns a non-`CodeGraph` (i.e., raw str), `run()` short-circuits and returns the value.

Testing
- Added unit tests verifying:
  - `dry_run()` returns the expected plan metadata.
  - Components are called in order and receive the expected context.

---

## Issue #13 — JoernParser enhancements and raw-export handling

What changed
1. `JoernParser` now accepts `source_code` (in-memory snippet) and `language` fields.
2. Added `export_format` parameter: `'dot'` (default), `'json'`, `'xml'` for raw exports.
3. Added configurable `parse_timeout_seconds` and `export_timeout_seconds` and robust subprocess error messages.
4. For raw `export_format`, parser returns the raw artifact (string); pipeline short-circuits.
5. Preserved legacy hooks (e.g., `_generate_dot_file`) to minimize breakage.

Why these choices
- In-memory parsing (`source_code`) makes interactive experiments and notebooks much easier.
- Raw exports are useful when consumers want Joern’s native artifacts (JSON/XML) for downstream tooling.
- Explicit timeouts and clear errors avoid flakiness in CI and make debugging easier.
- Short-circuiting is an explicit, efficient opt-in path — it avoids building a graph when unnecessary.

How it was implemented (step-by-step)
- Step 1: Extend `JoernParser` signature to accept `source_code`, `language`, `export_format`, and timeouts.
- Step 2: Add internal branches in `run()` / `build_graph()`:
  - If `export_format` is `'dot'` then run Joern export and parse DOT into a `CodeGraph`.
  - If `export_format` is `'json'` or `'xml'`, run Joern export and load the raw artifact, return it as a `str`.
- Step 3: Implement subprocess wrappers with timeouts and capture `stdout`/`stderr` for informative exceptions.
- Step 4: Keep legacy hooks intact so tests or external scripts that call older methods continue working.

Testing
- Unit tests simulate Joern outputs by monkeypatching the subprocess call paths.
- Integration tests for real Joern runs are kept gated behind `RUN_REAL_JOERN=1` and a `joern`-on-PATH precondition.

---

## Component call flow and short-circuit semantics (detailed)

- The pipeline always begins by calling the first component with either `file_path` or `source_code`.
- The pipeline inspects the return value:
  - If it is a `CodeGraph` instance, the pipeline proceeds and resolves `target_node_id` as needed.
  - If it is any other type (commonly `str` for raw exports), the pipeline returns that value immediately.

Rationale for short-circuit
- Efficiency: avoids unnecessary graph construction and transformations when the user asked for a raw artifact.
- Explicitness: user's choice of `export_format` signals intent — the short-circuit responds to that intent.

Alternative behaviors considered (and why we didn't pick them by default)
- Always parse raw JSON/XML into a `CodeGraph`: more consistent but wasteful for users who only want raw output.
- Return a path to a temp file: explicit and avoids huge in-memory strings but adds I/O handling complexity for consumers.
- Add a `force_graph` boolean to always generate a `CodeGraph`: acceptable as a future opt-in.

---

## File-level summary (key files to review)
- `src/codegraphene/core.py` — `BaseComponent`, `CodeGraph` utilities
- `src/codegraphene/pipeline.py` — `GraphPipeline`, dry-run, sequencing, short-circuit
- `src/codegraphene/parsers/base.py` — `BaseParser` adapters
- `src/codegraphene/parsers/joern.py` — Joern parser changes (source_code, language, export_format, timeouts)
- `src/codegraphene/trimmers/khop.py` — K-hop trimmer adapted to `BaseTrimmer`
- `src/codegraphene/serializers/text.py` — `CodeReconstructionSerializer` formatting and filters
- `tests/` — updated unit tests and guarded integration tests

---

## Trade-offs, alternatives, and recommended next steps

Trade-offs
- Pros: modularity, testability, explicit opt-in raw-export, clearer failure modes, backwards compatibility.
- Cons: short-circuit introduces a branching behavior in pipeline output types (sometimes `CodeGraph`, sometimes `str`). Consumers must account for this.

Recommended next steps
1. Decide the dependency policy for `pydot`/`pyparsing` (`pydot==1.4.2` pin vs CI matrix).
2. Add the two recommended tests:
   - `tests/test_pipeline_short_circuit.py` (unit, monkeypatched parser returns `str`).
   - `tests/test_integration_joern_raw_export.py` (guarded integration).
3. Optionally expose a `force_graph` argument on `JoernParser` if consumers want consistent `CodeGraph` output even in raw-export scenarios.

---

## Current problems & open questions

The implementation is functional, but there are several outstanding problems and questions that the team should resolve. These items are prioritized roughly by risk and impact:

- Dependency stability: `pydot`/`pyparsing`/`networkx` compatibility is brittle. We currently recommend pinning `pydot==1.4.2` but the team must decide whether to pin now or run a CI dependency matrix to identify compatible combinations.
- Joern availability in CI: real Joern integration tests are gated with `RUN_REAL_JOERN=1`. Decide whether to provide a dedicated CI job with Joern installed, or keep these tests out of default CI.
- Raw-export API contract: confirm preferred behavior for `JoernParser(export_format=...)` when raw formats are requested:
  - Return an in-memory raw `str` (current behavior), OR
  - Write artifact to a temp file and return the file path, OR
  - Parse the raw artifact into a structured object (e.g., dict for JSON) and return that.
  The decision affects memory usage, I/O semantics, and downstream consumer code.
- Short-circuit expectation: communicate to downstream consumers that pipeline may return a non-`CodeGraph` result; or add a `force_graph` option to always produce `CodeGraph` objects even for raw exports.
- Tests to add & CI policy: add the recommended unit short-circuit test and the guarded integration raw-export test. Decide whether integration tests should run in a specialized CI runner.
- Demo and teaching material: `ReadMeStudentKit.md` exists, but we should add a small runnable demo script or notebook to show `dry_run()`, in-memory parsing, and raw-export behavior.
- Backwards compatibility coverage: verify any external scripts that relied on old hooks (e.g., `_generate_dot_file`) still work; consider adding small compatibility tests.
- Timeout tuning: the chosen default parse/export timeouts need validation across environments; CI may require different settings than local dev machines.
- Artifact size and memory: raw exports (JSON) for large projects may be very large in-memory; a file-path return option may be preferred for large codebases.
- Security considerations: if we run Joern or other tools on untrusted code in CI, ensure sandboxing or limit inputs; validate subprocess call handling to avoid command injection.

Please review and assign owners or decisions for the bullets above so we can complete the remaining tasks and stabilize the branch.
