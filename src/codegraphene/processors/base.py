"""Base processor interface for CodeGraphene (issue #14, second half).

A Processor differs from a Cleaner (see
``codegraphene.cleaners.base.BaseCleaner``) in that it MAY change type
and/or plurality: ``Text -> Graph``, ``Text -> list[Text]``,
``list[Graph] -> Graph``, etc. Cleaners are always Item -> Item.

Modality bookkeeping deliberately stays a plain string label reusing the
existing ``describe()["input_type"]``/``["output_type"]`` fields already on
BaseComponent, rather than a new Modality class hierarchy: the issue asks for
"basic categorization", and ``dry_run()`` only needs a label to print, not a
type system enforcing compatibility at pipeline-build time. If stricter
checking is wanted later, it can be layered on top of these strings without
changing this base class.
"""

from abc import abstractmethod
from typing import Any

from ..core import BaseComponent


class BaseProcessor(BaseComponent):
    """Base class for components that transform between modalities."""

    @abstractmethod
    def process(self, item: Any) -> Any:
        """Transform *item* and return the result. May change type/plurality."""

    def run(self, current_graph=None, **context):
        """Run the processor on whatever the previous step produced."""
        item = current_graph if current_graph is not None else context.get("source_code")
        if item is None:
            raise ValueError(
                "BaseProcessor.run() requires an input item via 'current_graph' "
                "or 'source_code' in context."
            )
        return self.process(item)

    def describe(self) -> dict:
        info = super().describe()
        info.update({"capabilities": ["transform"]})
        return info
