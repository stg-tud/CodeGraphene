"""Example: run a basic CodeGraphene pipeline on a Joern DOT export."""

from codegraphene import (
    GraphPipeline,
    JoernParser,
    KHopTrimmer,
    CodeReconstructionSerializer,
)

pipeline = GraphPipeline(
    parser=JoernParser(),
    trimmer=KHopTrimmer(hops=2),
    serializer=CodeReconstructionSerializer(),
)

# Replace "export.dot" with the path to a real Joern DOT file.
result = pipeline.run("export.dot", target_node_id="42")
print(result)
