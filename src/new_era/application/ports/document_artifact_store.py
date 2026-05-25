from __future__ import annotations

from typing import Protocol

from new_era.domain.documents import DocumentArtifactRecord, DocumentArtifactStatus


class DocumentArtifactStore(Protocol):
    def save(self, record: DocumentArtifactRecord) -> None:
        raise NotImplementedError

    def get(self, artifact_id: str) -> DocumentArtifactRecord | None:
        raise NotImplementedError

    def update(self, record: DocumentArtifactRecord) -> None:
        raise NotImplementedError

    def list_by_session(
        self,
        *,
        user_id: str,
        session_id: str,
        status: DocumentArtifactStatus | None = None,
    ) -> list[DocumentArtifactRecord]:
        raise NotImplementedError
