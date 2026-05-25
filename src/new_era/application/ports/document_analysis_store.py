from __future__ import annotations

from new_era.domain.documents.models import DocumentAnalysisRecord


class DocumentAnalysisStore:
    def save(self, record: DocumentAnalysisRecord) -> None:
        raise NotImplementedError

    def get(self, analysis_id: str) -> DocumentAnalysisRecord | None:
        raise NotImplementedError

    def list_by_session(self, session_id: str) -> list[DocumentAnalysisRecord]:
        raise NotImplementedError
