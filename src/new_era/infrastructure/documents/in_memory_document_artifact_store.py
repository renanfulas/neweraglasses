from __future__ import annotations

from dataclasses import dataclass, field

from new_era.application.ports.document_artifact_store import DocumentArtifactStore
from new_era.domain.documents import DocumentArtifactRecord, DocumentArtifactStatus


@dataclass(slots=True)
class InMemoryDocumentArtifactStore(DocumentArtifactStore):
    records: dict[str, DocumentArtifactRecord] = field(default_factory=dict)

    def save(self, record: DocumentArtifactRecord) -> None:
        self.records[record.artifact_id] = record

    def get(self, artifact_id: str) -> DocumentArtifactRecord | None:
        return self.records.get(artifact_id)

    def update(self, record: DocumentArtifactRecord) -> None:
        self.records[record.artifact_id] = record

    def list_by_session(
        self,
        *,
        user_id: str,
        session_id: str,
        status: DocumentArtifactStatus | None = None,
    ) -> list[DocumentArtifactRecord]:
        matching_records = [
            record
            for record in self.records.values()
            if record.user_id == user_id and record.session_id == session_id
        ]
        if status is not None:
            matching_records = [record for record in matching_records if record.status == status]
        return sorted(
            matching_records,
            key=lambda record: (record.created_at, record.artifact_id),
            reverse=True,
        )
