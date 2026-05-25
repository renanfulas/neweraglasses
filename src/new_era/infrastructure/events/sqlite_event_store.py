from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from new_era.application.ports import EventCursor, EventStore
from new_era.domain.events import Event, EventType


@dataclass(frozen=True, slots=True)
class SQLiteEventStore(EventStore):
    database_path: Path | str

    def __post_init__(self) -> None:
        path = Path(self.database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        object.__setattr__(self, "database_path", path)
        self._initialize_schema()

    def append(self, event: Event) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO events (
                    event_id,
                    event_type,
                    event_version,
                    correlation_id,
                    trace_id,
                    user_id,
                    session_id,
                    module,
                    policy_version,
                    model_version,
                    created_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.event_type.value,
                    event.event_version,
                    event.correlation_id,
                    event.trace_id,
                    event.user_id,
                    event.session_id,
                    event.module,
                    event.policy_version,
                    event.model_version,
                    event.created_at.isoformat(),
                    json.dumps(dict(event.metadata), sort_keys=True),
                ),
            )
            connection.commit()

    def list_events(
        self,
        user_id: str | None = None,
        session_id: str | None = None,
        trace_id: str | None = None,
        module: str | None = None,
        event_types: set[EventType] | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        after: EventCursor | None = None,
        limit: int | None = None,
    ) -> list[Event]:
        clauses: list[str] = []
        params: list[object] = []

        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(user_id)
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if trace_id is not None:
            clauses.append("trace_id = ?")
            params.append(trace_id)
        if module is not None:
            clauses.append("module = ?")
            params.append(module)
        if event_types is not None:
            if not event_types:
                return []
            placeholders = ", ".join("?" for _ in event_types)
            clauses.append(f"event_type IN ({placeholders})")
            params.extend(sorted(event_type.value for event_type in event_types))
        if created_after is not None:
            clauses.append("created_at >= ?")
            params.append(created_after.isoformat())
        if created_before is not None:
            clauses.append("created_at <= ?")
            params.append(created_before.isoformat())
        if after is not None:
            clauses.append(
                """
                (
                    created_at > ?
                    OR (
                        created_at = ?
                        AND rowid > COALESCE(
                            (SELECT rowid FROM events WHERE event_id = ?),
                            -1
                        )
                    )
                )
                """.strip()
            )
            params.extend([after[0].isoformat(), after[0].isoformat(), after[1]])

        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit_clause = "LIMIT ?" if limit is not None else ""
        if limit is not None:
            params.append(limit)

        query = f"""
            SELECT
                event_id,
                event_type,
                event_version,
                correlation_id,
                trace_id,
                user_id,
                session_id,
                module,
                policy_version,
                model_version,
                created_at,
                metadata_json
            FROM events
            {where_clause}
            ORDER BY created_at ASC, rowid ASC
            {limit_clause}
        """

        with closing(self._connect()) as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_event(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_schema(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    event_version INTEGER NOT NULL,
                    correlation_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    module TEXT NOT NULL,
                    policy_version TEXT,
                    model_version TEXT,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            connection.commit()
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_events_session_created
                ON events (session_id, created_at, event_id)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_events_user_created
                ON events (user_id, created_at, event_id)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_events_trace_created
                ON events (trace_id, created_at, event_id)
                """
            )
            connection.commit()

    def _row_to_event(self, row: sqlite3.Row) -> Event:
        return Event(
            event_type=EventType(row["event_type"]),
            user_id=row["user_id"],
            session_id=row["session_id"],
            module=row["module"],
            correlation_id=row["correlation_id"],
            trace_id=row["trace_id"],
            metadata=json.loads(row["metadata_json"]),
            event_id=row["event_id"],
            event_version=row["event_version"],
            policy_version=row["policy_version"],
            model_version=row["model_version"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
