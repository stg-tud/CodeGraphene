# TODO: add type support OOTB
# type: ignore
from codegraphene import (
    GraphPipeline, 
    JoernParser, 
    KHopTrimmer, 
    CodeReconstructionSerializer
)

def create_dummy_file():
    """Creates a dummy python file to test the pipeline."""
    code = """def calculate_discount(price, is_member):
    discount = 0.0
    if is_member:
        discount = price * 0.10
    final_price = price - discount
    return final_price
    """
    with open("dummy.py", "w") as f:
        f.write(code)

def main():
    create_dummy_file()

    pipeline = GraphPipeline(
        parser=JoernParser(),
        trimmer=KHopTrimmer(hops=3, edge_types=["AST", "CFG"]),
        serializer=CodeReconstructionSerializer()
    )

    try:
        prompt_text = pipeline.run("dummy.py", target_line=4)
        
        print("\n=== FINAL LLM CONTEXT ===")
        print(prompt_text)
        print("=========================")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()