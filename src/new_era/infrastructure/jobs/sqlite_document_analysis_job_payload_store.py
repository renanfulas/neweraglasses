from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from new_era.application.ports import (
    DocumentAnalysisJobPayload,
    DocumentAnalysisJobPayloadStore,
)
from new_era.domain.attention import AttentionMode


@dataclass(frozen=True, slots=True)
class SQLiteDocumentAnalysisJobPayloadStore(DocumentAnalysisJobPayloadStore):
    database_path: Path | str

    def __post_init__(self) -> None:
        path = Path(self.database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        object.__setattr__(self, "database_path", path)
        self._initialize_schema()

    def save(self, payload: DocumentAnalysisJobPayload) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO document_analysis_job_payloads (
                    job_id,
                    user_id,
                    session_id,
                    artifact_label,
                    source_type,
                    artifact_id,
                    document_text,
                    document_image_base64,
                    confidence,
                    attention_mode,
                    recent_category_count,
                    observation_id,
                    correlation_id,
                    trace_id,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.job_id,
                    payload.user_id,
                    payload.session_id,
                    payload.artifact_label,
                    payload.source_type,
                    payload.artifact_id,
                    payload.document_text,
                    payload.document_image_base64,
                    payload.confidence,
                    payload.mode.value,
                    payload.recent_category_count,
                    payload.observation_id,
                    payload.correlation_id,
                    payload.trace_id,
                    payload.created_at.isoformat(),
                ),
            )
            connection.commit()

    def get(self, job_id: str) -> DocumentAnalysisJobPayload | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    job_id,
                    user_id,
                    session_id,
                    artifact_label,
                    source_type,
                    artifact_id,
                    document_text,
                    document_image_base64,
                    confidence,
                    attention_mode,
                    recent_category_count,
                    observation_id,
                    correlation_id,
                    trace_id,
                    created_at
                FROM document_analysis_job_payloads
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
        return self._row_to_payload(row) if row is not None else None

    def delete(self, job_id: str) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                "DELETE FROM document_analysis_job_payloads WHERE job_id = ?",
                (job_id,),
            )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_schema(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS document_analysis_job_payloads (
                    job_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    artifact_label TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    artifact_id TEXT NULL,
                    document_text TEXT,
                    document_image_base64 TEXT,
                    confidence REAL,
                    attention_mode TEXT NOT NULL,
                    recent_category_count INTEGER NOT NULL,
                    observation_id TEXT,
                    correlation_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            columns = connection.execute(
                "PRAGMA table_info(document_analysis_job_payloads)"
            ).fetchall()
            if not any(column["name"] == "artifact_id" for column in columns):
                connection.execute(
                    """
                    ALTER TABLE document_analysis_job_payloads
                    ADD COLUMN artifact_id TEXT NULL
                    """
                )
            connection.commit()

    def _row_to_payload(self, row: sqlite3.Row) -> DocumentAnalysisJobPayload:
        return DocumentAnalysisJobPayload(
            job_id=row["job_id"],
            user_id=row["user_id"],
            session_id=row["session_id"],
            artifact_label=row["artifact_label"],
            source_type=row["source_type"],
            artifact_id=row["artifact_id"],
            document_text=row["document_text"],
            document_image_base64=row["document_image_base64"],
            confidence=row["confidence"],
            mode=AttentionMode(row["attention_mode"]),
            recent_category_count=row["recent_category_count"],
            observation_id=row["observation_id"],
            correlation_id=row["correlation_id"],
            trace_id=row["trace_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
