import time
import os
from codegraphene.core import NodeGranularity
from codegraphene.parsers.joern import JoernParser
from codegraphene.trimmers.khop import KHopTrimmer
from codegraphene.serializers.text import CodeReconstructionSerializer

def run_benchmark():
    target_file = "examples/sample_code.py"
    
    if not os.path.exists(target_file):
        print(f"Error: Could not find {target_file}")
        return

    print("--- PHASE 1.2: PREPROCESSING LATENCY & BASE GRAPH SIZE ---")
    parser = JoernParser(granularity=NodeGranularity.LINE)
    
    # Measure Joern parsing time
    start_time = time.time()
    base_graph = parser.run(file_path=target_file)
    parse_duration = time.time() - start_time
    
    print(f"JoernParser Execution Time: {parse_duration:.2f} seconds")
    print(f"Base Graph (LINE) - Nodes: {base_graph.nx_graph.number_of_nodes()}, Edges: {base_graph.nx_graph.number_of_edges()}\n")

    print("--- PHASE 1.3: K-HOP CONTEXT BLOAT & COMPRESSION ---")
    target_line = 63
    
    # Read original file to calculate compression baseline
    with open(target_file, "r", encoding="utf-8") as f:
        original_code = f.read()
    print(f"Original File Size: {len(original_code)} characters\n")

    # Resolve the target node ID manually to isolate the trimmer
    target_nodes = parser.granularity.find_target_nodes(base_graph, target_line)
    if not target_nodes:
        print(f"Error: Target line {target_line} not found in graph.")
        return
    
    target_id = target_nodes[0].id

    # Iterate through K-hops to demonstrate bloat
    for k in [1, 2, 3]:
        trimmer = KHopTrimmer(hops=k)
        serializer = CodeReconstructionSerializer(granularity=NodeGranularity.LINE)
        
        # Trim and serialize
        trimmed_graph = trimmer.run(current_graph=base_graph, target_node_id=target_id)
        serialized_prompt = serializer.run(current_graph=trimmed_graph)
        
        # Extract metrics
        nodes = trimmed_graph.nx_graph.number_of_nodes()
        edges = trimmed_graph.nx_graph.number_of_edges()
        prompt_len = len(serialized_prompt)
        compression_ratio = (1 - (prompt_len / len(original_code))) * 100
        
        print(f"K = {k}:")
        print(f"  Sub-graph Size: {nodes} Nodes, {edges} Edges")
        print(f"  Prompt Length:  {prompt_len} characters")
        print(f"  Compression:    {compression_ratio:.2f}% text reduction\n")

if __name__ == "__main__":
    run_benchmark()