from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from new_era.application.ports.event_store import EventCursor, EventStore
from new_era.domain.events.models import Event, EventType


@dataclass(slots=True)
class InMemoryEventStore(EventStore):
    events: list[Event] = field(default_factory=list)

    def append(self, event: Event) -> None:
        self.events.append(event)

    def list_events(
        self,
        *,
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
        filtered_events = self.events
        if user_id is not None:
            filtered_events = [event for event in filtered_events if event.user_id == user_id]
        if session_id is not None:
            filtered_events = [event for event in filtered_events if event.session_id == session_id]
        if trace_id is not None:
            filtered_events = [event for event in filtered_events if event.trace_id == trace_id]
        if module is not None:
            filtered_events = [event for event in filtered_events if event.module == module]
        if event_types is not None:
            filtered_events = [event for event in filtered_events if event.event_type in event_types]
        if created_after is not None:
            filtered_events = [
                event for event in filtered_events if event.created_at >= created_after
            ]
        if created_before is not None:
            filtered_events = [
                event for event in filtered_events if event.created_at <= created_before
            ]
        filtered_events = sorted(filtered_events, key=lambda event: event.created_at)
        if after is not None:
            cursor_index = next(
                (
                    index
                    for index, event in enumerate(filtered_events)
                    if event.created_at == after[0] and event.event_id == after[1]
                ),
                None,
            )
            if cursor_index is not None:
                filtered_events = filtered_events[cursor_index + 1 :]
            else:
                filtered_events = [
                    event
                    for event in filtered_events
                    if (event.created_at, event.event_id) > after
                ]
        if limit is not None:
            filtered_events = filtered_events[:limit]
        return list(filtered_events)
