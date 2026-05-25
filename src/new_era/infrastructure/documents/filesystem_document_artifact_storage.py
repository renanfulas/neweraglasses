from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from new_era.application.ports.local_document_artifact_storage import (
    LocalDocumentArtifactStorage,
    StoredDocumentArtifact,
)


def _safe_path_token(value: str) -> str:
    safe_value = "".join(
        character if character.isalnum() or character in "._-" else "-"
        for character in value.strip()
    ).strip(".-")
    return safe_value or "artifact"


@dataclass(frozen=True, slots=True)
class FilesystemDocumentArtifactStorage(LocalDocumentArtifactStorage):
    root_dir: Path | str

    def __post_init__(self) -> None:
        root_dir = Path(self.root_dir).resolve()
        root_dir.mkdir(parents=True, exist_ok=True)
        object.__setattr__(self, "root_dir", root_dir)

    def save(
        self,
        *,
        artifact_id: str,
        session_id: str,
        artifact_label: str,
        payload: bytes,
    ) -> StoredDocumentArtifact:
        session_dir = self.root_dir / _safe_path_token(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{artifact_id}_{_safe_path_token(artifact_label)}"
        file_path = (session_dir / file_name).resolve()
        file_path.write_bytes(payload)
        storage_key = file_path.relative_to(self.root_dir).as_posix()
        return StoredDocumentArtifact(
            storage_key=storage_key,
            local_path=str(file_path),
            size_bytes=len(payload),
        )

    def delete(self, *, storage_key: str) -> None:
        file_path = (self.root_dir / storage_key).resolve()
        root_dir = self.root_dir.resolve()
        if root_dir not in file_path.parents and file_path != root_dir:
            raise ValueError("storage_key_resolves_outside_root")
        if file_path.exists():
            file_path.unlink()
