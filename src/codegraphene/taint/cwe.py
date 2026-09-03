"""
CWE → source/sink name templates for taint extraction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CWETemplate:
    cwe_id: str
    name: str
    description: str
    sources: List[str] = field(default_factory=list)
    sinks: List[str] = field(default_factory=list)
    include_parameters_as_sources: bool = True


CWE_TEMPLATES: Dict[str, CWETemplate] = {
    "CWE-119": CWETemplate(
        cwe_id="CWE-119",
        name="Buffer Overflow",
        description="Improper restriction of operations within the bounds of a memory buffer",
        sources=[],
        sinks=["memcpy", "strcpy", "strncpy", "sprintf",
               "gets", "strcat", "strncat", "memmove", "wmemcpy"],
        include_parameters_as_sources=True,
    ),
    "CWE-476": CWETemplate(
        cwe_id="CWE-476",
        name="NULL Pointer Dereference",
        description="Dereferencing a pointer that may be NULL",
        # Master-thesis sinks this on `cpg.call.argument.isIdentifier`, which is
        # too generic to mirror by name. We approximate by treating common
        # dereferencing calls as sinks; users can override via explicit sinks.
        sources=["malloc", "calloc", "realloc", "strdup", "fopen", "mmap"],
        sinks=["memcpy", "memmove", "strcpy", "strncpy", "strlen", "free"],
        include_parameters_as_sources=True,
    ),
    "CWE-787": CWETemplate(
        cwe_id="CWE-787",
        name="Out-of-bounds Write",
        description="Writing data past the end or before the beginning of a buffer",
        sources=["recv", "read", "fread", "fgets", "scanf"],
        sinks=["memcpy", "strcpy", "memset", "write",
               "strncpy", "sprintf", "snprintf", "strcat", "memmove"],
        include_parameters_as_sources=True,
    ),
    "CWE-20": CWETemplate(
        cwe_id="CWE-20",
        name="Improper Input Validation",
        description="Failure to validate or incorrectly validating input",
        sources=["recv", "read", "fread", "fgets", "scanf", "getenv", "argv"],
        sinks=["system", "exec", "popen", "execve",
               "execvp", "open", "fopen", "connect", "memcpy", "strcpy"],
        include_parameters_as_sources=True,
    ),
    "CWE-125": CWETemplate(
        cwe_id="CWE-125",
        name="Out-of-bounds Read",
        description="Reading data past the end or before the beginning of a buffer",
        sources=["malloc", "calloc", "realloc", "alloca"],
        sinks=["memcpy", "memmove", "read", "fread", "strncpy", "memcmp"],
        include_parameters_as_sources=True,
    ),
}


def get_template(cwe_id: str) -> Optional[CWETemplate]:
    return CWE_TEMPLATES.get(cwe_id)


def supported_cwes() -> List[str]:
    return list(CWE_TEMPLATES.keys())
