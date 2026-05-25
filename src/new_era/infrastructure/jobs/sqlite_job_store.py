from __future__ import annotations

from collections.abc import Collection
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from new_era.application.ports import JobStore
from new_era.domain.jobs import JobRecord, JobStatus, JobType


@dataclass(frozen=True, slots=True)
class SQLiteJobStore(JobStore):
    database_path: Path | str

    def __post_init__(self) -> None:
        path = Path(self.database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        object.__setattr__(self, "database_path", path)
        self._initialize_schema()

    def save(self, job: JobRecord) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    job_id,
                    job_type,
                    status,
                    user_id,
                    session_id,
                    module,
                    idempotency_key,
                    attempts,
                    max_attempts,
                    timeout_seconds,
                    retry_backoff_seconds,
                    result_id,
                    error_code,
                    error_message,
                    created_at,
                    updated_at,
                    started_at,
                    completed_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._job_values(job),
            )
            connection.commit()

    def get(self, job_id: str) -> JobRecord | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    job_id,
                    job_type,
                    status,
                    user_id,
                    session_id,
                    module,
                    idempotency_key,
                    attempts,
                    max_attempts,
                    timeout_seconds,
                    retry_backoff_seconds,
                    result_id,
                    error_code,
                    error_message,
                    created_at,
                    updated_at,
                    started_at,
                    completed_at,
                    metadata_json
                FROM jobs
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
        return self._row_to_job(row) if row is not None else None

    def update(self, job: JobRecord) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE jobs
                SET
                    job_type = ?,
                    status = ?,
                    user_id = ?,
                    session_id = ?,
                    module = ?,
                    idempotency_key = ?,
                    attempts = ?,
                    max_attempts = ?,
                    timeout_seconds = ?,
                    retry_backoff_seconds = ?,
                    result_id = ?,
                    error_code = ?,
                    error_message = ?,
                    created_at = ?,
                    updated_at = ?,
                    started_at = ?,
                    completed_at = ?,
                    metadata_json = ?
                WHERE job_id = ?
                """,
                self._job_values(job)[1:] + (job.job_id,),
            )
            connection.commit()

    def find_by_idempotency_key(
        self,
        *,
        job_type: JobType,
        user_id: str,
        session_id: str,
        idempotency_key: str,
    ) -> JobRecord | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    job_id,
                    job_type,
                    status,
                    user_id,
                    session_id,
                    module,
                    idempotency_key,
                    attempts,
                    max_attempts,
                    timeout_seconds,
                    retry_backoff_seconds,
                    result_id,
                    error_code,
                    error_message,
                    created_at,
                    updated_at,
                    started_at,
                    completed_at,
                    metadata_json
                FROM jobs
                WHERE job_type = ? AND user_id = ? AND session_id = ? AND idempotency_key = ?
                ORDER BY created_at DESC, job_id DESC
                LIMIT 1
                """,
                (job_type.value, user_id, session_id, idempotency_key),
            ).fetchone()
        return self._row_to_job(row) if row is not None else None

    def list_by_session(
        self,
        *,
        user_id: str,
        session_id: str,
        module: str | None = None,
        status: JobStatus | None = None,
        limit: int | None = None,
    ) -> list[JobRecord]:
        clauses = ["user_id = ?", "session_id = ?"]
        values: list[object] = [user_id, session_id]
        if module is not None:
            clauses.append("module = ?")
            values.append(module)
        if status is not None:
            clauses.append("status = ?")
            values.append(status.value)

        query = f"""
            SELECT
                job_id,
                job_type,
                status,
                user_id,
                session_id,
                module,
                idempotency_key,
                attempts,
                max_attempts,
                timeout_seconds,
                retry_backoff_seconds,
                result_id,
                error_code,
                error_message,
                created_at,
                updated_at,
                started_at,
                completed_at,
                metadata_json
            FROM jobs
            WHERE {" AND ".join(clauses)}
            ORDER BY created_at DESC, job_id DESC
        """
        if limit is not None:
            query += " LIMIT ?"
            values.append(limit)

        with closing(self._connect()) as connection:
            rows = connection.execute(query, tuple(values)).fetchall()
        return [self._row_to_job(row) for row in rows]

    def count_by_session_statuses(
        self,
        *,
        user_id: str,
        session_id: str,
        statuses: Collection[JobStatus],
        module: str | None = None,
    ) -> int:
        status_values = [status.value for status in statuses]
        if not status_values:
            return 0

        clauses = ["user_id = ?", "session_id = ?"]
        values: list[object] = [user_id, session_id]
        if module is not None:
            clauses.append("module = ?")
            values.append(module)

        placeholders = ", ".join("?" for _ in status_values)
        clauses.append(f"status IN ({placeholders})")
        values.extend(status_values)

        query = f"""
            SELECT COUNT(*)
            FROM jobs
            WHERE {" AND ".join(clauses)}
        """
        with closing(self._connect()) as connection:
            return int(connection.execute(query, tuple(values)).fetchone()[0])

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_schema(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    module TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    max_attempts INTEGER NOT NULL,
                    timeout_seconds REAL NOT NULL,
                    retry_backoff_seconds REAL NOT NULL,
                    result_id TEXT,
                    error_code TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            connection.commit()
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_jobs_user_session_idempotency
                ON jobs (job_type, user_id, session_id, idempotency_key, created_at, job_id)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_jobs_session_created
                ON jobs (session_id, created_at, job_id)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_jobs_user_session_created
                ON jobs (user_id, session_id, created_at, job_id)
                """
            )
            connection.commit()

    def _job_values(self, job: JobRecord) -> tuple[object, ...]:
        return (
            job.job_id,
            job.job_type.value,
            job.status.value,
            job.user_id,
            job.session_id,
            job.module,
            job.idempotency_key,
            job.attempts,
            job.max_attempts,
            job.timeout_seconds,
            job.retry_backoff_seconds,
            job.result_id,
            job.error_code,
            job.error_message,
            job.created_at.isoformat(),
            job.updated_at.isoformat(),
            job.started_at.isoformat() if job.started_at else None,
            job.completed_at.isoformat() if job.completed_at else None,
            json.dumps(dict(job.metadata), sort_keys=True),
        )

    def _row_to_job(self, row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            job_id=row["job_id"],
            job_type=JobType(row["job_type"]),
            status=JobStatus(row["status"]),
            user_id=row["user_id"],
            session_id=row["session_id"],
            module=row["module"],
            idempotency_key=row["idempotency_key"],
            attempts=row["attempts"],
            max_attempts=row["max_attempts"],
            timeout_seconds=row["timeout_seconds"],
            retry_backoff_seconds=row["retry_backoff_seconds"],
            result_id=row["result_id"],
            error_code=row["error_code"],
            error_message=row["error_message"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            started_at=(
                datetime.fromisoformat(row["started_at"])
                if row["started_at"] is not None
                else None
            ),
            completed_at=(
                datetime.fromisoformat(row["completed_at"])
                if row["completed_at"] is not None
                else None
            ),
            metadata=json.loads(row["metadata_json"]),
        )
