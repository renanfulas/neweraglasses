"""Document analysis read-model adapters."""

from new_era.infrastructure.documents.filesystem_document_artifact_storage import (
    FilesystemDocumentArtifactStorage,
)
from new_era.infrastructure.documents.in_memory_document_analysis_store import (
    InMemoryDocumentAnalysisStore,
)
from new_era.infrastructure.documents.in_memory_document_artifact_store import (
    InMemoryDocumentArtifactStore,
)
from new_era.infrastructure.documents.sqlite_document_analysis_store import (
    SQLiteDocumentAnalysisStore,
)
from new_era.infrastructure.documents.sqlite_document_artifact_store import (
    SQLiteDocumentArtifactStore,
)

__all__ = [
    "FilesystemDocumentArtifactStorage",
    "InMemoryDocumentAnalysisStore",
    "InMemoryDocumentArtifactStore",
    "SQLiteDocumentAnalysisStore",
    "SQLiteDocumentArtifactStore",
]
