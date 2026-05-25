"""Document analysis read-model adapters."""

from new_era.infrastructure.documents.in_memory_document_analysis_store import (
    InMemoryDocumentAnalysisStore,
)
from new_era.infrastructure.documents.sqlite_document_analysis_store import (
    SQLiteDocumentAnalysisStore,
)

__all__ = ["InMemoryDocumentAnalysisStore", "SQLiteDocumentAnalysisStore"]
