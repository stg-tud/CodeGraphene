"""Taint-flow extraction over an exported CPG.

Computes data-flow paths from source nodes (e.g. method parameters, tainted
input calls) to sink nodes (e.g. memcpy, system) by walking REACHING_DEF
edges on the NetworkX CPG produced by JoernParser. No Joern server required.
"""

from .flows import TaintFlow, TaintFlowElement
from .cwe import CWE_TEMPLATES, CWETemplate, get_template, supported_cwes
from .extractor import TaintExtractor
from .joern_query import FlowElement, JoernFlow, find_taint_flows

__all__ = [
    "TaintFlow",
    "TaintFlowElement",
    "TaintExtractor",
    "CWETemplate",
    "CWE_TEMPLATES",
    "get_template",
    "supported_cwes",
    "JoernFlow",
    "FlowElement",
    "find_taint_flows",
]
