"""Public API for the codegraphene package."""

from .core import CodeGraph
from .pipeline import GraphPipeline
from .parsers.joern import JoernParser
from .trimmers.khop import KHopTrimmer
from .trimmers.taint_flow import TaintFlowTrimmer
from .trimmers.block_aware import BlockAwareTrimmer
from .serializers.text import CodeReconstructionSerializer
from .core import NodeGranularity
from .blocks import CodeBlock, analyze_c_code, find_enclosing_blocks, smallest_enclosing_block
from .taint import (
    TaintFlow,
    TaintFlowElement,
    TaintExtractor,
    CWETemplate,
    CWE_TEMPLATES,
    get_template,
    supported_cwes,
)

__all__ = [
    "CodeGraph",
    "GraphPipeline",
    "JoernParser",
    "KHopTrimmer",
    "TaintFlowTrimmer",
    "BlockAwareTrimmer",
    "CodeReconstructionSerializer",
    "NodeGranularity",
    "CodeBlock",
    "analyze_c_code",
    "find_enclosing_blocks",
    "smallest_enclosing_block",
    "TaintFlow",
    "TaintFlowElement",
    "TaintExtractor",
    "CWETemplate",
    "CWE_TEMPLATES",
    "get_template",
    "supported_cwes",
]
