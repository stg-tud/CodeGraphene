# CodeGraphene

**CodeGraphene** is a modular pipeline for trimming and serializing Code Property Graphs (CPGs) for use with Large Language Models (LLMs).

## Overview

This package provides a composable pipeline to:
1. **Parse** source code into a `CodeGraph` using tools like Joern.
2. **Trim** the graph to a relevant subgraph (e.g., k-hop neighbourhood around a target node).
3. **Serialize** the trimmed graph into a text representation suitable for LLM prompts.

## Installation

```bash
pip install codegraphene
```

## Quick Start

```python
from codegraphene import GraphPipeline, JoernParser, KHopTrimmer, CodeReconstructionSerializer

pipeline = GraphPipeline(
    parser=JoernParser(),
    trimmer=KHopTrimmer(hops=2),
    serializer=CodeReconstructionSerializer(),
)
result = pipeline.run("export.dot", target_node_id="42")
print(result)
```

## License

Apache 2.0
