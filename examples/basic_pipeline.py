# TODO: add type support OOTB
# type: ignore
from codegraphene import (
    GraphPipeline, 
    JoernParser, 
    KHopTrimmer, 
    CodeReconstructionSerializer
)

def main():
    # 1. Configure the pipeline 
    # Use k-hop trimmer, looking 2 hops away, following AST and CFG (Control Flow) edges.
    pipeline = GraphPipeline(
        parser=JoernParser(),
        trimmer=KHopTrimmer(hops=2, edge_types=["AST", "CFG"]),
        serializer=CodeReconstructionSerializer()
    )

    # 2. Run the pipeline
    # Point this to your export.dot file. 
    try:
        prompt_text = pipeline.run("export.dot", target_line=4)
        
        print("\n=== FINAL LLM CONTEXT ===")
        print(prompt_text)
        print("=========================")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()