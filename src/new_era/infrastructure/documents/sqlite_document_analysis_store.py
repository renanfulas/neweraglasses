from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from new_era.application.ports import DocumentAnalysisStore
from new_era.domain.documents import (
    ContractFinding,
    ContractFindingType,
    ContractReviewAnalysis,
    DocumentAnalysisRecord,
)


@dataclass(frozen=True, slots=True)
class SQLiteDocumentAnalysisStore(DocumentAnalysisStore):
    database_path: Path | str

    def __post_init__(self) -> None:
        path = Path(self.database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        object.__setattr__(self, "database_path", path)
        self._initialize_schema()

    def save(self, record: DocumentAnalysisRecord) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO document_analyses (
                    analysis_id,
                    user_id,
                    session_id,
                    observation_id,
                    trace_id,
                    source_type,
                    artifact_id,
                    created_at,
                    analysis_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.analysis_id,
                    record.user_id,
                    record.session_id,
                    record.observation_id,
                    record.trace_id,
                    record.source_type,
                    record.artifact_id,
                    record.created_at.isoformat(),
                    json.dumps(record.to_dict()["analysis"], sort_keys=True),
                ),
            )
            connection.commit()

    def get(self, analysis_id: str) -> DocumentAnalysisRecord | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    analysis_id,
                    user_id,
                    session_id,
                    observation_id,
                    trace_id,
                    source_type,
                    artifact_id,
                    created_at,
                    analysis_json
                FROM document_analyses
                WHERE analysis_id = ?
                """,
                (analysis_id,),
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def list_by_session(self, *, session_id: str) -> list[DocumentAnalysisRecord]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    analysis_id,
                    user_id,
                    session_id,
                    observation_id,
                    trace_id,
                    source_type,
                    artifact_id,
                    created_at,
                    analysis_json
                FROM document_analyses
                WHERE session_id = ?
                ORDER BY created_at DESC, analysis_id DESC
                """,
                (session_id,),
            ).fetchall()
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
                CREATE TABLE IF NOT EXISTS document_analyses (
                    analysis_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    observation_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    artifact_id TEXT NULL,
                    created_at TEXT NOT NULL,
                    analysis_json TEXT NOT NULL
                )
                """
            )
            if not self._has_column(connection, "document_analyses", "artifact_id"):
                connection.execute(
                    """
                    ALTER TABLE document_analyses
                    ADD COLUMN artifact_id TEXT NULL
                    """
                )
            connection.commit()
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_document_analyses_session_created
                ON document_analyses (session_id, created_at, analysis_id)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_document_analyses_user_created
                ON document_analyses (user_id, created_at, analysis_id)
                """
            )
            connection.commit()

    def _row_to_record(self, row: sqlite3.Row) -> DocumentAnalysisRecord:
        analysis_data = json.loads(row["analysis_json"])
        return DocumentAnalysisRecord(
            analysis_id=row["analysis_id"],
            user_id=row["user_id"],
            session_id=row["session_id"],
            observation_id=row["observation_id"],
            trace_id=row["trace_id"],
            source_type=row["source_type"],
            artifact_id=row["artifact_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            analysis=self._analysis_from_dict(analysis_data),
        )

    def _has_column(
        self,
        connection: sqlite3.Connection,
        table_name: str,
        column_name: str,
    ) -> bool:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        return any(row["name"] == column_name for row in rows)

    def _analysis_from_dict(self, data: dict[str, object]) -> ContractReviewAnalysis:
        findings = tuple(
            ContractFinding(
                finding_type=ContractFindingType(item["finding_type"]),
                label=item["label"],
                excerpt=item["excerpt"],
                confidence=item["confidence"],
            )
            for item in data.get("findings", [])
        )
        return ContractReviewAnalysis(
            extracted_text=data["extracted_text"],
            source_confidence=data["source_confidence"],
            review_confidence=data["review_confidence"],
            summary_title=data["summary_title"],
            summary_body=data["summary_body"],
            findings=findings,
            parsing_notes=tuple(data.get("parsing_notes", [])),
        )
