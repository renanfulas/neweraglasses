from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from new_era.application.ports.document_artifact_store import DocumentArtifactStore
from new_era.domain.documents import (
    DocumentArtifactRecord,
    DocumentArtifactStatus,
)


@dataclass(frozen=True, slots=True)
class SQLiteDocumentArtifactStore(DocumentArtifactStore):
    database_path: Path | str

    def __post_init__(self) -> None:
        path = Path(self.database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        object.__setattr__(self, "database_path", path)
        self._initialize_schema()

    def save(self, record: DocumentArtifactRecord) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO document_artifacts (
                    artifact_id,
                    user_id,
                    session_id,
                    artifact_label,
                    source_type,
                    content_type,
                    size_bytes,
                    storage_key,
                    local_path,
                    status,
                    expires_at,
                    deleted_at,
                    created_at,
                    updated_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.artifact_id,
                    record.user_id,
                    record.session_id,
                    record.artifact_label,
                    record.source_type,
                    record.content_type,
                    record.size_bytes,
                    record.storage_key,
                    record.local_path,
                    record.status.value,
                    record.expires_at.isoformat() if record.expires_at else None,
                    record.deleted_at.isoformat() if record.deleted_at else None,
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                    json.dumps(dict(record.metadata), sort_keys=True),
                ),
            )
            connection.commit()

    def get(self, artifact_id: str) -> DocumentArtifactRecord | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    artifact_id,
                    user_id,
                    session_id,
                    artifact_label,
                    source_type,
                    content_type,
                    size_bytes,
                    storage_key,
                    local_path,
                    status,
                    expires_at,
                    deleted_at,
                    created_at,
                    updated_at,
                    metadata_json
                FROM document_artifacts
                WHERE artifact_id = ?
                """,
                (artifact_id,),
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def update(self, record: DocumentArtifactRecord) -> None:
        self.save(record)

    def list_by_session(
        self,
        *,
        user_id: str,
        session_id: str,
        status: DocumentArtifactStatus | None = None,
    ) -> list[DocumentArtifactRecord]:
        query = """
            SELECT
                artifact_id,
                user_id,
                session_id,
                artifact_label,
                source_type,
                content_type,
                size_bytes,
                storage_key,
                local_path,
                status,
                expires_at,
                deleted_at,
                created_at,
                updated_at,
                metadata_json
            FROM document_artifacts
            WHERE user_id = ? AND session_id = ?
        """
        parameters: list[object] = [user_id, session_id]
        if status is not None:
            query += " AND status = ?"
            parameters.append(status.value)
        query += " ORDER BY created_at DESC, artifact_id DESC"

        with closing(self._connect()) as connection:
            rows = connection.execute(query, tuple(parameters)).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_schema(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS document_artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    artifact_label TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    storage_key TEXT NOT NULL,
                    local_path TEXT NOT NULL,
                    status TEXT NOT NULL,
                    expires_at TEXT NULL,
                    deleted_at TEXT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_document_artifacts_session_created
                ON document_artifacts (user_id, session_id, created_at, artifact_id)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_document_artifacts_session_status
                ON document_artifacts (user_id, session_id, status, created_at, artifact_id)
                """
            )
            connection.commit()

    def _row_to_record(self, row: sqlite3.Row) -> DocumentArtifactRecord:
        return DocumentArtifactRecord(
            artifact_id=row["artifact_id"],
            user_id=row["user_id"],
            session_id=row["session_id"],
            artifact_label=row["artifact_label"],
            source_type=row["source_type"],
            content_type=row["content_type"],
            size_bytes=row["size_bytes"],
            storage_key=row["storage_key"],
            local_path=row["local_path"],
            status=DocumentArtifactStatus(row["status"]),
            expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
            deleted_at=datetime.fromisoformat(row["deleted_at"]) if row["deleted_at"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            metadata=json.loads(row["metadata_json"]),
        )
