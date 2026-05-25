from __future__ import annotations

from dataclasses import dataclass

from new_era.application.ports import DocumentAnalysisStore
from new_era.domain.documents import DocumentAnalysisRecord


@dataclass(frozen=True, slots=True)
class GetDocumentAnalysis:
    analysis_store: DocumentAnalysisStore

    def execute(self, analysis_id: str) -> DocumentAnalysisRecord | None:
        return self.analysis_store.get(analysis_id)


@dataclass(frozen=True, slots=True)
class ListDocumentAnalysesBySession:
    analysis_store: DocumentAnalysisStore

    def execute(self, session_id: str) -> list[DocumentAnalysisRecord]:
        return self.analysis_store.list_by_session(session_id=session_id)
