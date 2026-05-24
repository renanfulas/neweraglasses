from __future__ import annotations

from dataclasses import dataclass, field

from new_era.application.ports.event_store import EventStore
from new_era.domain.events.models import Event


@dataclass(slots=True)
class InMemoryEventStore(EventStore):
    events: list[Event] = field(default_factory=list)

    def append(self, event: Event) -> None:
        self.events.append(event)

    def list_events(
        self,
        *,
        session_id: str | None = None,
        trace_id: str | None = None,
    ) -> list[Event]:
        filtered_events = self.events
        if session_id is not None:
            filtered_events = [event for event in filtered_events if event.session_id == session_id]
        if trace_id is not None:
            filtered_events = [event for event in filtered_events if event.trace_id == trace_id]
        return list(filtered_events)
