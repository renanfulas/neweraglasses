from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock

from new_era.application.ports import SessionCursor, SessionStore
from new_era.domain.sessions import UserSession


@dataclass(slots=True)
class InMemorySessionStore(SessionStore):
    sessions: dict[str, UserSession] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def save(self, session: UserSession) -> None:
        with self._lock:
            self.sessions[session.session_id] = session

    def get(self, session_id: str) -> UserSession | None:
        with self._lock:
            return self.sessions.get(session_id)

    def update(self, session: UserSession) -> None:
        with self._lock:
            self.sessions[session.session_id] = session

    def list_by_user(
        self,
        *,
        user_id: str,
        module: str | None = None,
        after: SessionCursor | None = None,
        limit: int | None = None,
    ) -> list[UserSession]:
        with self._lock:
            sessions = [session for session in self.sessions.values() if session.user_id == user_id]
        if module is not None:
            sessions = [session for session in sessions if session.module == module]
        sessions = sorted(
            sessions,
            key=lambda session: (session.updated_at, session.session_id),
            reverse=True,
        )
        if after is not None:
            sessions = [
                session
                for session in sessions
                if (session.updated_at, session.session_id) < after
            ]
        if limit is not None:
            sessions = sessions[:limit]
        return sessions
