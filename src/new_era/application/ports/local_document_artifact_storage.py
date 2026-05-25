from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class StoredDocumentArtifact:
    storage_key: str
    local_path: str
    size_bytes: int


class LocalDocumentArtifactStorage(Protocol):
    def save(
        self,
        *,
        artifact_id: str,
        session_id: str,
        artifact_label: str,
        payload: bytes,
    ) -> StoredDocumentArtifact:
        raise NotImplementedError

    def delete(self, *, storage_key: str) -> None:
        raise NotImplementedError
