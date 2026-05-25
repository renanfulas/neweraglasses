from __future__ import annotations

from dataclasses import dataclass, field

from new_era.application.ports import DocumentAnalysisStore
from new_era.domain.documents import DocumentAnalysisRecord


@dataclass(slots=True)
class InMemoryDocumentAnalysisStore(DocumentAnalysisStore):
    records: dict[str, DocumentAnalysisRecord] = field(default_factory=dict)

    def save(self, record: DocumentAnalysisRecord) -> None:
        self.records[record.analysis_id] = record

    def get(self, analysis_id: str) -> DocumentAnalysisRecord | None:
        return self.records.get(analysis_id)

    def list_by_session(self, *, session_id: str) -> list[DocumentAnalysisRecord]:
        return sorted(
            [record for record in self.records.values() if record.session_id == session_id],
            key=lambda record: record.created_at,
            reverse=True,
        )
