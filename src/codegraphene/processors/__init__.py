"""Public API for the processors sub-package (issue #14, second half)."""

from .base import BaseProcessor
from .method_splitter import MethodSplitterProcessor

__all__ = ["BaseProcessor", "MethodSplitterProcessor"]
