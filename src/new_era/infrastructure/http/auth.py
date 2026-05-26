from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hmac import compare_digest
from pathlib import Path
from threading import Lock
from uuid import uuid4


AUTH_SESSION_COOKIE = "newera_session"
DEFAULT_AUTH_SESSION_TTL = timedelta(hours=12)


@dataclass(frozen=True, slots=True)
class LocalPasswordAuthConfig:
    user_id: str | None = None
    password: str | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self.user_id and self.password)

    def authenticate(self, *, user_id: str, password: str) -> bool:
        if not self.is_configured or self.user_id is None or self.password is None:
            return False
        return compare_digest(user_id, self.user_id) and compare_digest(
            password,
            self.password,
        )


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    subject_id: str
    user_id: str
    auth_session_id: str
    auth_method: str
    issued_at: datetime
    expires_at: datetime
    scopes: tuple[str, ...] = ("companion",)

    def to_dict(self) -> dict[str, object]:
        return {
            "subject_id": self.subject_id,
            "user_id": self.user_id,
            "auth_session_id": self.auth_session_id,
            "auth_method": self.auth_method,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "scopes": list(self.scopes),
        }


@dataclass(frozen=True, slots=True)
class AuthSessionRecord:
    auth_session_id: str
    subject_id: str
    user_id: str
    auth_method: str
    issued_at: datetime
    expires_at: datetime
    scopes: tuple[str, ...] = ("companion",)

    def is_expired(self, *, now: datetime | None = None) -> bool:
        current_time = now or datetime.now(UTC)
        return current_time >= self.expires_at

    def to_identity(self) -> AuthenticatedIdentity:
        return AuthenticatedIdentity(
            subject_id=self.subject_id,
            user_id=self.user_id,
            auth_session_id=self.auth_session_id,
            auth_method=self.auth_method,
            issued_at=self.issued_at,
            expires_at=self.expires_at,
            scopes=self.scopes,
        )


@dataclass(slots=True)
class InMemoryAuthSessionStore:
    ttl: timedelta = DEFAULT_AUTH_SESSION_TTL
    _records: dict[str, AuthSessionRecord] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def create(
        self,
        *,
        user_id: str,
        auth_method: str = "local_demo",
        scopes: tuple[str, ...] = ("companion",),
    ) -> AuthSessionRecord:
        issued_at = datetime.now(UTC)
        record = AuthSessionRecord(
            auth_session_id=f"authsess_{uuid4().hex}",
            subject_id=user_id,
            user_id=user_id,
            auth_method=auth_method,
            issued_at=issued_at,
            expires_at=issued_at + self.ttl,
            scopes=scopes,
        )
        with self._lock:
            self._records[record.auth_session_id] = record
        return record

    def get(self, auth_session_id: str) -> AuthSessionRecord | None:
        with self._lock:
            record = self._records.get(auth_session_id)
            if record is None:
                return None
            if record.is_expired():
                self._records.pop(auth_session_id, None)
                return None
            return record

    def invalidate(self, auth_session_id: str) -> None:
        with self._lock:
            self._records.pop(auth_session_id, None)


@dataclass(frozen=True, slots=True)
class SQLiteAuthSessionStore:
    database_path: Path | str
    ttl: timedelta = DEFAULT_AUTH_SESSION_TTL

    def __post_init__(self) -> None:
        path = Path(self.database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        object.__setattr__(self, "database_path", path)
        self._initialize_schema()

    def create(
        self,
        *,
        user_id: str,
        auth_method: str = "local_demo",
        scopes: tuple[str, ...] = ("companion",),
    ) -> AuthSessionRecord:
        issued_at = datetime.now(UTC)
        record = AuthSessionRecord(
            auth_session_id=f"authsess_{uuid4().hex}",
            subject_id=user_id,
            user_id=user_id,
            auth_method=auth_method,
            issued_at=issued_at,
            expires_at=issued_at + self.ttl,
            scopes=scopes,
        )
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO auth_sessions (
                    auth_session_id,
                    subject_id,
                    user_id,
                    auth_method,
                    issued_at,
                    expires_at,
                    scopes_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.auth_session_id,
                    record.subject_id,
                    record.user_id,
                    record.auth_method,
                    record.issued_at.isoformat(),
                    record.expires_at.isoformat(),
                    json.dumps(list(record.scopes)),
                ),
            )
            connection.commit()
        return record

    def get(self, auth_session_id: str) -> AuthSessionRecord | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    auth_session_id,
                    subject_id,
                    user_id,
                    auth_method,
                    issued_at,
                    expires_at,
                    scopes_json
                FROM auth_sessions
                WHERE auth_session_id = ?
                """,
                (auth_session_id,),
            ).fetchone()
            if row is None:
                return None
            record = self._row_to_record(row)
            if record.is_expired():
                connection.execute(
                    "DELETE FROM auth_sessions WHERE auth_session_id = ?",
                    (auth_session_id,),
                )
                connection.commit()
                return None
            return record

    def invalidate(self, auth_session_id: str) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                "DELETE FROM auth_sessions WHERE auth_session_id = ?",
                (auth_session_id,),
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
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    auth_session_id TEXT PRIMARY KEY,
                    subject_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    auth_method TEXT NOT NULL,
                    issued_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    scopes_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_expires
                ON auth_sessions (user_id, expires_at, auth_session_id)
                """
            )
            connection.commit()

    def _row_to_record(self, row: sqlite3.Row) -> AuthSessionRecord:
        return AuthSessionRecord(
            auth_session_id=row["auth_session_id"],
            subject_id=row["subject_id"],
            user_id=row["user_id"],
            auth_method=row["auth_method"],
            issued_at=datetime.fromisoformat(row["issued_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]),
            scopes=tuple(json.loads(row["scopes_json"])),
        )
