"""Tell a book's main text apart from its front and back matter."""

from anyaudiobook.matter.classifier import classify_documents
from anyaudiobook.matter.models import (
    DEFAULT_SKIP,
    Decision,
    FilterOptions,
    MatterKind,
    Verdict,
)
from anyaudiobook.models import Document, Reference

__all__ = [
    "DEFAULT_SKIP",
    "Decision",
    "Document",
    "FilterOptions",
    "MatterKind",
    "Reference",
    "Verdict",
    "classify_documents",
]
