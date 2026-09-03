"""Public API for the codegraphene package."""

from .blocks import (
    CodeBlock,
    analyze_c_code,
    find_enclosing_blocks,
    smallest_enclosing_block,
)
from .cleaners.base import BaseCleaner
from .cleaners.black_formatter import BlackFormatter
from .core import BaseComponent, CodeGraph, NodeGranularity
from .parsers.joern import JoernParser
from .pipeline import GraphPipeline
from .processors.base import BaseProcessor
from .processors.method_splitter import MethodSplitterProcessor
from .serializers.text import CodeReconstructionSerializer
from .taint import (
    CWE_TEMPLATES,
    CWETemplate,
    FlowElement,
    JoernFlow,
    TaintExtractor,
    TaintFlow,
    TaintFlowElement,
    find_taint_flows,
    get_template,
    supported_cwes,
)
from .trimmers.block_aware import BlockAwareTrimmer
from .trimmers.khop import KHopTrimmer
from .trimmers.slicer import ProgramSlicer
from .trimmers.taint_flow import TaintFlowTrimmer

__all__ = [
    "CWE_TEMPLATES",
    "BaseCleaner",
    "BaseComponent",
    "BaseProcessor",
    "BlackFormatter",
    "BlockAwareTrimmer",
    "CWETemplate",
    "CodeBlock",
    "CodeGraph",
    "CodeReconstructionSerializer",
    "FlowElement",
    "GraphPipeline",
    "JoernFlow",
    "JoernParser",
    "KHopTrimmer",
    "MethodSplitterProcessor",
    "NodeGranularity",
    "ProgramSlicer",
    "TaintExtractor",
    "TaintFlow",
    "TaintFlowElement",
    "TaintFlowTrimmer",
    "analyze_c_code",
    "find_enclosing_blocks",
    "find_taint_flows",
    "get_template",
    "smallest_enclosing_block",
    "supported_cwes",
]
