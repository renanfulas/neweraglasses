from __future__ import annotations

from datetime import datetime
from typing import TypeAlias

from new_era.domain.events.models import Event, EventType

EventCursor: TypeAlias = tuple[datetime, str]


class EventStore:
    def append(self, event: Event) -> None:
        raise NotImplementedError

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
        raise NotImplementedError
