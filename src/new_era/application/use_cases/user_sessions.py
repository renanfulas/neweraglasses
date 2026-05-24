from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import uuid4

from new_era.application.ports import SessionStore
from new_era.domain.sessions import UserSession

DEFAULT_SESSION_LIMIT = 25
MAX_SESSION_LIMIT = 100


class SessionOwnershipError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class UserSessionReadModel:
    session_id: str
    user_id: str
    module: str
    title: str
    created_at: str
    updated_at: str
    metadata: dict[str, object]

    @classmethod
    def from_session(cls, session: UserSession) -> "UserSessionReadModel":
        return cls(
            session_id=session.session_id,
            user_id=session.user_id,
            module=session.module,
            title=session.title,
            created_at=session.created_at.isoformat(),
            updated_at=session.updated_at.isoformat(),
            metadata=dict(session.metadata),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "module": self.module,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class UserSessionPageReadModel:
    user_id: str
    session_count: int
    next_cursor: str | None
    sessions: tuple[UserSessionReadModel, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "user_id": self.user_id,
            "session_count": self.session_count,
            "next_cursor": self.next_cursor,
            "sessions": [session.to_dict() for session in self.sessions],
        }


def normalize_session_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_SESSION_LIMIT
    if limit < 1:
        raise ValueError("limit must be at least 1")
    return min(limit, MAX_SESSION_LIMIT)


def encode_session_cursor(session: UserSession) -> str:
    value = f"{session.updated_at.isoformat()}|{session.session_id}"
    return urlsafe_b64encode(value.encode("utf-8")).decode("ascii")


def decode_session_cursor(cursor: str | None) -> tuple[datetime, str] | None:
    if cursor is None:
        return None
    try:
        decoded = urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        updated_at_text, session_id = decoded.split("|", 1)
        return datetime.fromisoformat(updated_at_text), session_id
    except Exception as exc:
        raise ValueError("invalid session cursor") from exc


@dataclass(frozen=True, slots=True)
class StartUserSession:
    session_store: SessionStore

    def execute(
        self,
        *,
        user_id: str,
        module: str,
        title: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> UserSession:
        session_title = title or default_session_title(module)
        existing_session = self.session_store.get(session_id) if session_id else None

        if existing_session is not None:
            if existing_session.user_id != user_id:
                raise SessionOwnershipError("session does not belong to user")
            touched_session = replace(
                existing_session,
                module=module or existing_session.module,
                title=title if title is not None else existing_session.title,
                metadata={**dict(existing_session.metadata), **(metadata or {})},
                updated_at=datetime.now(UTC),
            )
            self.session_store.update(touched_session)
            return touched_session

        session = UserSession(
            user_id=user_id,
            session_id=session_id or f"session_{uuid4().hex}",
            module=module,
            title=session_title,
            metadata=metadata or {},
        )
        self.session_store.save(session)
        return session


@dataclass(frozen=True, slots=True)
class GetUserSession:
    session_store: SessionStore

    def execute(self, *, user_id: str, session_id: str) -> UserSession | None:
        session = self.session_store.get(session_id)
        if session is None or session.user_id != user_id:
            return None
        return session


@dataclass(frozen=True, slots=True)
class ListUserSessions:
    session_store: SessionStore

    def execute(
        self,
        *,
        user_id: str,
        module: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> UserSessionPageReadModel:
        normalized_limit = normalize_session_limit(limit)
        sessions = self.session_store.list_by_user(
            user_id=user_id,
            module=module,
            after=decode_session_cursor(cursor),
            limit=normalized_limit + 1,
        )
        has_more = len(sessions) > normalized_limit
        page_sessions = sessions[:normalized_limit]
        return UserSessionPageReadModel(
            user_id=user_id,
            session_count=len(page_sessions),
            next_cursor=encode_session_cursor(page_sessions[-1])
            if has_more and page_sessions
            else None,
            sessions=tuple(UserSessionReadModel.from_session(session) for session in page_sessions),
        )


def default_session_title(module: str) -> str:
    if module == "grocery":
        return "Grocery session"
    if module == "documents":
        return "Document review session"
    return f"{module.replace('_', ' ').title()} session"
