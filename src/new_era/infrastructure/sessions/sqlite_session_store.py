from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from new_era.application.ports import SessionCursor, SessionStore
from new_era.domain.sessions import UserSession


@dataclass(frozen=True, slots=True)
class SQLiteSessionStore(SessionStore):
    database_path: Path | str

    def __post_init__(self) -> None:
        path = Path(self.database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        object.__setattr__(self, "database_path", path)
        self._initialize_schema()

    def save(self, session: UserSession) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO user_sessions (
                    session_id,
                    user_id,
                    module,
                    title,
                    created_at,
                    updated_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.user_id,
                    session.module,
                    session.title,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                    json.dumps(dict(session.metadata), sort_keys=True),
                ),
            )
            connection.commit()

    def get(self, session_id: str) -> UserSession | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    session_id,
                    user_id,
                    module,
                    title,
                    created_at,
                    updated_at,
                    metadata_json
                FROM user_sessions
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        return self._row_to_session(row) if row is not None else None

    def update(self, session: UserSession) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE user_sessions
                SET
                    user_id = ?,
                    module = ?,
                    title = ?,
                    created_at = ?,
                    updated_at = ?,
                    metadata_json = ?
                WHERE session_id = ?
                """,
                (
                    session.user_id,
                    session.module,
                    session.title,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                    json.dumps(dict(session.metadata), sort_keys=True),
                    session.session_id,
                ),
            )
            connection.commit()

    def list_by_user(
        self,
        *,
        user_id: str,
        module: str | None = None,
        after: SessionCursor | None = None,
        limit: int | None = None,
    ) -> list[UserSession]:
        clauses = ["user_id = ?"]
        params: list[object] = [user_id]

        if module is not None:
            clauses.append("module = ?")
            params.append(module)
        if after is not None:
            clauses.append("(updated_at < ? OR (updated_at = ? AND session_id < ?))")
            params.extend([after[0].isoformat(), after[0].isoformat(), after[1]])

        limit_clause = "LIMIT ?" if limit is not None else ""
        if limit is not None:
            params.append(limit)

        query = f"""
            SELECT
                session_id,
                user_id,
                module,
                title,
                created_at,
                updated_at,
                metadata_json
            FROM user_sessions
            WHERE {' AND '.join(clauses)}
            ORDER BY updated_at DESC, session_id DESC
            {limit_clause}
        """
        with closing(self._connect()) as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_session(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_schema(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS user_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    module TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            connection.commit()
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_user_sessions_user_updated
                ON user_sessions (user_id, updated_at, session_id)
                """
            )
            connection.commit()

    def _row_to_session(self, row: sqlite3.Row) -> UserSession:
        return UserSession(
            user_id=row["user_id"],
            session_id=row["session_id"],
            module=row["module"],
            title=row["title"],
            metadata=json.loads(row["metadata_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
