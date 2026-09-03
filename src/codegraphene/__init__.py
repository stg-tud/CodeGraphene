"""Public API for the codegraphene package."""

from .core import BaseComponent, CodeGraph
from .pipeline import GraphPipeline
from .parsers.joern import JoernParser
from .trimmers.khop import KHopTrimmer
from .trimmers.slicer import ProgramSlicer
from .trimmers.taint_flow import TaintFlowTrimmer
from .trimmers.block_aware import BlockAwareTrimmer
from .serializers.text import CodeReconstructionSerializer

from .cleaners.base import BaseCleaner
from .cleaners.black_formatter import BlackFormatter
from .processors.base import BaseProcessor
from .processors.method_splitter import MethodSplitterProcessor
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
    "BaseComponent",
    "CodeGraph",
    "GraphPipeline",
    "JoernParser",
    "KHopTrimmer",
    "ProgramSlicer",
    "TaintFlowTrimmer",
    "BlockAwareTrimmer",
    "CodeReconstructionSerializer",
    "NodeGranularity",
    "BaseCleaner",
    "BlackFormatter",
    "BaseProcessor",
    "MethodSplitterProcessor",
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
