from __future__ import annotations

from datetime import datetime
from typing import Protocol

from new_era.domain.sessions import UserSession


SessionCursor = tuple[datetime, str]


class SessionStore(Protocol):
    def save(self, session: UserSession) -> None:
        raise NotImplementedError

    def get(self, session_id: str) -> UserSession | None:
        raise NotImplementedError

    def update(self, session: UserSession) -> None:
        raise NotImplementedError

    def list_by_user(
        self,
        *,
        user_id: str,
        module: str | None = None,
        after: SessionCursor | None = None,
        limit: int | None = None,
    ) -> list[UserSession]:
        raise NotImplementedError
