"""PDF Merger desktop utility."""

from .core import (
    ConversionError,
    MergeError,
    PageSelection,
    SUPPORTED_EXTENSIONS,
    inspect_source,
    merge_selected_pages,
    merge_sources,
)

__all__ = [
    "ConversionError",
    "MergeError",
    "PageSelection",
    "SUPPORTED_EXTENSIONS",
    "inspect_source",
    "merge_selected_pages",
    "merge_sources",
]
